#!/usr/bin/env python3
"""Authored fail-closed coverage for the privileged gateway promoter."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("promote_gateway.py")
SPEC = importlib.util.spec_from_file_location("promote_gateway_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("gateway promoter module is unavailable")
PROMOTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PROMOTER
SPEC.loader.exec_module(PROMOTER)


class GatewayPromoterCoverage(unittest.TestCase):
    def test_requirement_lock_accepts_only_the_fixed_hash_locked_package_set(self) -> None:
        lock = MODULE_PATH.with_name("sentry-requirements.lock").read_bytes()
        PROMOTER._validate_requirement_lock(lock)
        with self.assertRaisesRegex(PROMOTER.GatewayUpdateError, "fixed package set"):
            PROMOTER._validate_requirement_lock(
                lock + b"unexpected-package==1.0.0 --hash=sha256:" + b"a" * 64 + b"\n"
            )

    def test_interrupted_activated_transaction_restores_both_gateway_surfaces(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gateway-promoter-rollback.") as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            package = root / "package"
            package.mkdir()
            (package / "marker").write_text("new")
            package_backup = root / "package.previous"
            package_backup.mkdir()
            (package_backup / "marker").write_text("old")
            launcher = root / "launcher"
            launcher.write_text("new")
            launcher_backup = root / "launcher.previous"
            launcher_backup.write_text("old")
            journal = state / "transaction.json"
            journal.write_text(
                json.dumps(
                    {
                        "schema": "bears-plugin-gateway-update.v1",
                        "sha": "a" * 40,
                        "state": "activated",
                    }
                )
                + "\n"
            )
            journal.chmod(0o600)
            with mock.patch.multiple(
                PROMOTER,
                STATE_ROOT=state,
                JOURNAL_FILE=journal,
                PACKAGE_ROOT=package,
                PACKAGE_BACKUP=package_backup,
                LAUNCHER=launcher,
                LAUNCHER_BACKUP=launcher_backup,
            ), mock.patch.object(PROMOTER, "_validate_installed_file"):
                PROMOTER._recover_interrupted_transaction()
            self.assertEqual((package / "marker").read_text(), "old")
            self.assertEqual(launcher.read_text(), "old")
            self.assertFalse(journal.exists())

    def test_interrupted_committed_transaction_keeps_new_gateway(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gateway-promoter-commit.") as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            package = root / "package"
            package.mkdir()
            (package / "marker").write_text("new")
            package_backup = root / "package.previous"
            package_backup.mkdir()
            (package_backup / "marker").write_text("old")
            launcher = root / "launcher"
            launcher.write_text("new")
            launcher_backup = root / "launcher.previous"
            launcher_backup.write_text("old")
            journal = state / "transaction.json"
            journal.write_text(
                json.dumps(
                    {
                        "schema": "bears-plugin-gateway-update.v1",
                        "sha": "b" * 40,
                        "state": "committed",
                    }
                )
                + "\n"
            )
            journal.chmod(0o600)
            with mock.patch.multiple(
                PROMOTER,
                STATE_ROOT=state,
                JOURNAL_FILE=journal,
                PACKAGE_ROOT=package,
                PACKAGE_BACKUP=package_backup,
                LAUNCHER=launcher,
                LAUNCHER_BACKUP=launcher_backup,
            ), mock.patch.object(PROMOTER, "_validate_installed_file"):
                PROMOTER._recover_interrupted_transaction()
            self.assertEqual((package / "marker").read_text(), "new")
            self.assertEqual(launcher.read_text(), "new")
            self.assertFalse(package_backup.exists())
            self.assertFalse(launcher_backup.exists())
            self.assertFalse(journal.exists())


if __name__ == "__main__":
    unittest.main()
