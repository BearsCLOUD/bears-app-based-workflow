"""Regression tests for retiring the legacy managed AGENTS.md block."""

from __future__ import annotations

import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import time
import types
from types import SimpleNamespace
import unittest
from unittest import mock


if "sentry_sdk" not in sys.modules:
    sys.modules["sentry_sdk"] = types.ModuleType("sentry_sdk")

RUNNER_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(RUNNER_ROOT))

import promote_gateway  # noqa: E402
from bears_deploy import graph_instructions, promotion, publication, receipts  # noqa: E402
from bears_deploy.constants import (  # noqa: E402
    DEPLOY_RECEIPT_SCHEMA,
    LEGACY_DEPLOY_RECEIPT_SCHEMA,
    REPOSITORY,
    ROLE_GENERATIONS_DIR,
    ROLE_GRAPH_DEPLOY_RECEIPT_SCHEMA,
)
from bears_deploy.intent_io import (  # noqa: E402
    load_intent,
    persist_intent,
    save_instruction_removal_intent,
    save_intent,
)
from bears_deploy.models import DeployError  # noqa: E402
from bears_deploy.state_io import load_state, validate_deploy_receipt  # noqa: E402


def embedded_installer_validator() -> dict[str, object]:
    """Compile only the pure receipt validator from the installer heredoc."""
    installer = (RUNNER_ROOT / "install-runner.sh").read_text(encoding="utf-8")
    marker = "<<'PY'\n"
    start = installer.index(marker) + len(marker)
    source = installer[start : installer.index("\nPY\n", start)]
    tree = ast.parse(source)
    functions = {
        "fail",
        "strict_json",
        "validate_receipt_identity",
        "validate_destination_receipt",
    }
    constants = {
        "PLUGIN",
        "REPOSITORY",
        "LEGACY_RECEIPT_SCHEMA",
        "PRIOR_RECEIPT_SCHEMA",
        "GRAPH_RECEIPT_SCHEMA",
        "ROLE_GRAPH_RECEIPT_SCHEMA",
        "DEPLOY_RECEIPT_SCHEMA",
        "RECEIPT_FIELDS",
        "ROLE_RECEIPT_FIELDS",
        "GRAPH_RECEIPT_FIELDS",
    }
    selected = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in functions
    ]
    namespace: dict[str, object] = {
        "json": json,
        "re": __import__("re"),
        "STATE_DIR": "/var/lib/bears-plugin-deploy/ai1",
    }
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in constants
        ):
            namespace[node.targets[0].id] = ast.literal_eval(node.value)
    if not constants.issubset(namespace):
        raise AssertionError("installer receipt validator constants are incomplete")
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))
    exec(compile(module, "install-runner-receipt-validator", "exec"), namespace)
    return namespace


class GraphInstructionRetirementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.home = root / "codex-home"
        self.home.mkdir()
        self.state = root / "state"
        self.state.mkdir()
        self.state_fd = os.open(self.state, os.O_RDONLY | os.O_DIRECTORY)
        self.home_patch = mock.patch.object(graph_instructions, "CODEX_HOME", self.home)
        self.home_patch.start()
        self.intent = save_intent(self.state_fd, "a" * 40, None)
        self.unmanaged = b"# User instructions\n"
        self.block = (
            graph_instructions.BEGIN
            + b"\nLegacy managed behavior.\n"
            + graph_instructions.END
            + b"\n"
        )
        self.injected = self.unmanaged + b"\n" + self.block
        self.receipt = {
            "graph_block_sha256": hashlib.sha256(self.block).hexdigest(),
            "graph_separator_added": True,
        }

    def tearDown(self) -> None:
        self.home_patch.stop()
        os.close(self.state_fd)
        self.temporary.cleanup()

    def write_agents(self, value: bytes) -> None:
        (self.home / "AGENTS.md").write_bytes(value)

    def save_legacy_injection_intent(
        self,
        *,
        original: bytes,
        original_present: bool,
        desired: bytes,
    ) -> dict[str, object]:
        """Persist the pre-v5 journal shape with implicit desired presence."""
        updated = save_instruction_removal_intent(
            self.state_fd,
            self.intent,
            original=original,
            original_present=original_present,
            desired=desired,
            desired_present=True,
        )
        transaction = dict(updated["graph_transaction"])
        transaction.pop("desired_present")
        legacy = dict(updated)
        legacy["graph_transaction"] = transaction
        return persist_intent(self.state_fd, legacy)

    def test_v4_block_is_removed_and_rollback_is_exact(self) -> None:
        self.write_agents(self.injected)

        graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        intent = load_intent(self.state_fd)
        self.assertIsNotNone(intent["graph_transaction"])

        graph_instructions.restore_graph_preimage(intent)
        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.injected)

        graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)
        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)

    def test_graphless_update_does_not_read_agents(self) -> None:
        with mock.patch.object(
            graph_instructions,
            "_read_regular",
            side_effect=AssertionError("AGENTS.md must not be read"),
        ):
            graph_instructions.retire_graph_instructions(
                self.state_fd,
                {"schema": DEPLOY_RECEIPT_SCHEMA},
            )

    def test_absent_legacy_block_stays_absent(self) -> None:
        self.write_agents(self.unmanaged)

        graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        self.assertIsNone(load_intent(self.state_fd)["graph_transaction"])

    def test_drifted_legacy_block_fails_closed(self) -> None:
        self.write_agents(self.injected.replace(b"Legacy", b"Changed"))

        with self.assertRaises(DeployError):
            graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

    def test_interrupted_removal_converges_from_journal(self) -> None:
        self.write_agents(self.injected)
        publisher = graph_instructions._publish
        with mock.patch.object(
            graph_instructions,
            "_publish",
            side_effect=RuntimeError("simulated crash before CAS"),
        ):
            with self.assertRaises(RuntimeError):
                graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

        self.assertIsNotNone(load_intent(self.state_fd)["graph_transaction"])
        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.injected)

        with mock.patch.object(graph_instructions, "_publish", wraps=publisher):
            graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)
        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)

    def test_post_exchange_crash_cleans_retained_preimage(self) -> None:
        self.write_agents(self.injected)
        with mock.patch.object(
            graph_instructions,
            "finalize_publication",
            side_effect=RuntimeError("simulated crash after exchange"),
        ):
            with self.assertRaises(RuntimeError):
                graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        exchanges = list(self.home.glob(".AGENTS.md.bears-retirement.*.exchange"))
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(exchanges[0].read_bytes(), self.injected)

        graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        self.assertEqual(list(self.home.glob(".AGENTS.md.bears-retirement.*.exchange")), [])

    def test_uninstall_retry_cleans_retained_preimage(self) -> None:
        self.write_agents(self.injected)
        with mock.patch.object(
            graph_instructions,
            "finalize_publication",
            side_effect=RuntimeError("simulated uninstall crash after exchange"),
        ):
            with self.assertRaises(RuntimeError):
                graph_instructions.remove_graph_instructions(self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        exchanges = list(self.home.glob(".AGENTS.md.bears-uninstall.*.exchange"))
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(exchanges[0].read_bytes(), self.injected)

        graph_instructions.remove_graph_instructions(self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        self.assertEqual(list(self.home.glob(".AGENTS.md.bears-uninstall.*.exchange")), [])

    def test_interrupted_pre_v5_injection_is_reversed_then_retired(self) -> None:
        new_block = self.block.replace(b"Legacy", b"Refreshed")
        refreshed = self.unmanaged + b"\n" + new_block
        self.write_agents(refreshed)
        self.save_legacy_injection_intent(
            original=self.injected,
            original_present=True,
            desired=refreshed,
        )

        graph_instructions.retire_graph_instructions(self.state_fd, self.receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)

    def test_interrupted_pre_v5_refresh_accepts_new_v4_receipt(self) -> None:
        new_block = self.block.replace(b"Legacy", b"Refreshed")
        refreshed = self.unmanaged + b"\n" + new_block
        self.write_agents(refreshed)
        self.save_legacy_injection_intent(
            original=self.injected,
            original_present=True,
            desired=refreshed,
        )
        receipt = {
            "graph_block_sha256": hashlib.sha256(new_block).hexdigest(),
            "graph_separator_added": True,
        }

        graph_instructions.retire_graph_instructions(self.state_fd, receipt)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)
        transaction = load_intent(self.state_fd)["graph_transaction"]
        self.assertIsNotNone(transaction)
        self.assertEqual(
            graph_instructions._transaction_bytes(transaction),
            (refreshed, self.unmanaged),
        )

    def test_interrupted_legacy_injection_restores_missing_file(self) -> None:
        receipt = {
            "graph_block_sha256": hashlib.sha256(self.block).hexdigest(),
            "graph_separator_added": False,
        }
        self.write_agents(self.block)
        self.save_legacy_injection_intent(
            original=b"",
            original_present=False,
            desired=self.block,
        )
        remover = graph_instructions._remove_expected
        with mock.patch.object(
            graph_instructions,
            "_remove_expected",
            side_effect=RuntimeError("simulated crash before removal"),
        ):
            with self.assertRaises(RuntimeError):
                graph_instructions.retire_graph_instructions(self.state_fd, receipt)

        transaction = load_intent(self.state_fd)["graph_transaction"]
        self.assertFalse(transaction["desired_present"])
        self.assertTrue((self.home / "AGENTS.md").exists())

        with mock.patch.object(graph_instructions, "_remove_expected", wraps=remover):
            graph_instructions.retire_graph_instructions(self.state_fd, receipt)
        self.assertFalse((self.home / "AGENTS.md").exists())

    def test_post_rename_crash_cleans_missing_file_preimage(self) -> None:
        receipt = {
            "graph_block_sha256": hashlib.sha256(self.block).hexdigest(),
            "graph_separator_added": False,
        }
        self.write_agents(self.block)
        self.save_legacy_injection_intent(
            original=b"",
            original_present=False,
            desired=self.block,
        )

        def crash_after_rename(file_publication: object) -> None:
            publication.renameat2(
                file_publication.directory,
                file_publication.target,
                file_publication.exchange_name,
                publication.RENAME_NOREPLACE,
            )
            os.fsync(file_publication.directory)
            raise RuntimeError("simulated crash after removal rename")

        with mock.patch.object(
            graph_instructions,
            "rollback_publication",
            side_effect=crash_after_rename,
        ):
            with self.assertRaises(RuntimeError):
                graph_instructions.retire_graph_instructions(self.state_fd, receipt)

        self.assertFalse((self.home / "AGENTS.md").exists())
        exchanges = list(self.home.glob(".AGENTS.md.bears-retirement.*.exchange"))
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(exchanges[0].read_bytes(), self.block)

        graph_instructions.retire_graph_instructions(self.state_fd, receipt)

        self.assertFalse((self.home / "AGENTS.md").exists())
        self.assertEqual(list(self.home.glob(".AGENTS.md.bears-retirement.*.exchange")), [])

    def test_removal_fallback_does_not_resurrect_block_after_v5_receipt(self) -> None:
        self.write_agents(self.injected)
        active = save_instruction_removal_intent(
            self.state_fd,
            self.intent,
            original=self.injected,
            original_present=True,
            desired=self.unmanaged,
            desired_present=True,
        )
        self.write_agents(self.unmanaged)
        with (
            mock.patch.object(promotion, "load_state", return_value={"schema": DEPLOY_RECEIPT_SCHEMA}),
            mock.patch.object(promotion, "run_json"),
            mock.patch.object(promotion, "verify_removed"),
            mock.patch.object(promotion, "clear_owned_roles"),
            mock.patch.object(promotion, "clear_state"),
        ):
            promotion.remove_and_verify(self.state_fd, active)

        self.assertEqual((self.home / "AGENTS.md").read_bytes(), self.unmanaged)


class GraphlessReceiptTests(unittest.TestCase):
    def role_record(self) -> dict[str, object]:
        generation = "b" * 64
        source = {"git_oid": "c" * 40, "sha256": "d" * 64}
        return {
            "repository": REPOSITORY,
            "marketplace": "bears-app-based-workflow",
            "plugin": "bears-app-based-workflow",
            "sha": "a" * 40,
            "version": "0.5.0",
            "payload_fingerprint": "e" * 64,
            "role_generation": generation,
            "role_count": 1,
            "role_catalog_sha256": generation,
            "role_receipt_sha256": "f" * 64,
            "role_source_blobs": {
                ".codex-plugin/plugin.json": source,
                "agents/README.md": source,
                "agents/worker.toml": source,
                "role-definitions/capability-catalog.v1.json": source,
                "role-definitions/worker.json": source,
            },
            "role_profiles": [
                {
                    "name": "worker",
                    "config_file": str(ROLE_GENERATIONS_DIR / generation / "worker.toml"),
                    "git_oid": source["git_oid"],
                    "sha256": source["sha256"],
                }
            ],
        }

    def legacy_state_and_role_record(
        self,
    ) -> tuple[dict[str, object], dict[str, object], str, str]:
        full = self.role_record()
        version = "0.4.3+codex.20260711074119"
        legacy_fingerprint = "9" * 64
        current_fingerprint = str(full["payload_fingerprint"])
        state = {
            "schema": LEGACY_DEPLOY_RECEIPT_SCHEMA,
            "repository": full["repository"],
            "marketplace": full["marketplace"],
            "plugin": full["plugin"],
            "sha": full["sha"],
            "version": version,
            "payload_fingerprint": legacy_fingerprint,
        }
        role_record = {
            key: value
            for key, value in full.items()
            if key not in {"repository", "marketplace", "plugin", "sha", "version"}
        }
        return state, role_record, legacy_fingerprint, current_fingerprint

    def test_v5_receipt_rejects_graph_fields(self) -> None:
        receipt = {"schema": DEPLOY_RECEIPT_SCHEMA, **self.role_record()}
        self.assertIs(validate_deploy_receipt(receipt), receipt)

        receipt.update(
            graph_template_sha256="1" * 64,
            graph_block_sha256="2" * 64,
            graph_separator_added=False,
        )
        with self.assertRaises(DeployError):
            validate_deploy_receipt(receipt)

    def test_v4_receipt_remains_valid_migration_input(self) -> None:
        receipt = {
            "schema": ROLE_GRAPH_DEPLOY_RECEIPT_SCHEMA,
            **self.role_record(),
            "graph_template_sha256": "1" * 64,
            "graph_block_sha256": "2" * 64,
            "graph_separator_added": False,
        }
        self.assertIs(validate_deploy_receipt(receipt), receipt)

    def test_v1_recovery_migrates_to_graphless_v5(self) -> None:
        full = self.role_record()
        state = {
            "schema": LEGACY_DEPLOY_RECEIPT_SCHEMA,
            **{
                key: full[key]
                for key in (
                    "repository",
                    "marketplace",
                    "plugin",
                    "sha",
                    "version",
                    "payload_fingerprint",
                )
            },
        }
        role_record = {
            key: value
            for key, value in full.items()
            if key
            not in {"repository", "marketplace", "plugin", "sha", "version"}
        }
        with tempfile.TemporaryDirectory() as directory:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                durable = promotion.save_recovered_state(descriptor, state, role_record)
            finally:
                os.close(descriptor)

        self.assertEqual(durable["schema"], DEPLOY_RECEIPT_SCHEMA)
        self.assertNotIn("graph_block_sha256", durable)

    def test_v1_role_reconciliation_accepts_current_fingerprint(self) -> None:
        state, role_record, legacy_fingerprint, current_fingerprint = (
            self.legacy_state_and_role_record()
        )
        with tempfile.TemporaryDirectory() as directory:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                intent = save_intent(descriptor, str(state["sha"]), state)
                with (
                    mock.patch.object(promotion, "reconcile_roles", return_value=role_record),
                    mock.patch.object(
                        receipts,
                        "legacy_payload_fingerprint",
                        return_value=legacy_fingerprint,
                    ),
                ):
                    reconciled = promotion.reconcile_receipted_roles(
                        descriptor,
                        state,
                        intent,
                    )
                    self.assertFalse(
                        receipts.payload_fingerprint_matches_receipt(
                            {**state, "schema": DEPLOY_RECEIPT_SCHEMA},
                            current_fingerprint,
                        )
                    )
            finally:
                os.close(descriptor)

        self.assertEqual(reconciled, role_record)

    def test_v1_restore_accepts_legacy_fingerprint_and_normalizes(self) -> None:
        state, role_record, legacy_fingerprint, current_fingerprint = (
            self.legacy_state_and_role_record()
        )
        with tempfile.TemporaryDirectory() as directory:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                with (
                    mock.patch.object(promotion, "marketplace_row"),
                    mock.patch.object(promotion, "exact_remote"),
                    mock.patch.object(
                        promotion,
                        "git",
                        return_value=SimpleNamespace(stdout=b""),
                    ),
                    mock.patch.object(
                        promotion,
                        "git_text",
                        return_value=str(state["sha"]),
                    ),
                    mock.patch.object(
                        promotion,
                        "manifest",
                        return_value={"version": state["version"]},
                    ),
                    mock.patch.object(
                        promotion,
                        "payload_fingerprint",
                        return_value=current_fingerprint,
                    ),
                    mock.patch.object(promotion, "run_json"),
                    mock.patch.object(promotion, "verify_receipted_install"),
                    mock.patch.object(
                        promotion,
                        "reconcile_receipted_roles",
                        return_value=role_record,
                    ),
                    mock.patch.object(
                        receipts,
                        "legacy_payload_fingerprint",
                        return_value=legacy_fingerprint,
                    ),
                ):
                    promotion.restore_receipted_install(descriptor, state)
                durable = load_state(descriptor)
            finally:
                os.close(descriptor)

        self.assertIsNotNone(durable)
        self.assertEqual(durable["schema"], DEPLOY_RECEIPT_SCHEMA)
        self.assertEqual(durable["payload_fingerprint"], current_fingerprint)

    def test_v4_recovery_preserves_exact_graph_receipt(self) -> None:
        full = self.role_record()
        state = {
            "schema": ROLE_GRAPH_DEPLOY_RECEIPT_SCHEMA,
            **full,
            "graph_template_sha256": "1" * 64,
            "graph_block_sha256": "2" * 64,
            "graph_separator_added": False,
        }
        role_record = {
            key: value
            for key, value in full.items()
            if key
            not in {"repository", "marketplace", "plugin", "sha", "version"}
        }
        with tempfile.TemporaryDirectory() as directory:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                durable = promotion.save_recovered_state(descriptor, state, role_record)
            finally:
                os.close(descriptor)

        self.assertEqual(durable, state)


class EmbeddedInstallerReceiptTests(unittest.TestCase):
    def receipt(self, schema: str) -> dict[str, object]:
        source = {"git_oid": "c" * 40, "sha256": "d" * 64}
        value: dict[str, object] = {
            "schema": schema,
            "repository": "https://github.com/BearsCLOUD/bears-app-based-workflow.git",
            "marketplace": "bears-app-based-workflow",
            "plugin": "bears-app-based-workflow",
            "sha": "a" * 40,
            "version": {
                "bears-plugin-deploy-state.v1": "0.1.0+codex.20260711074119",
                "bears-plugin-deploy-state.v2": "0.2.0",
                "bears-plugin-deploy-state.v3": "0.3.0",
                "bears-plugin-deploy-state.v4": "0.4.0",
                "bears-plugin-deploy-state.v5": "0.5.0",
            }[schema],
            "payload_fingerprint": "e" * 64,
        }
        if schema == "bears-plugin-deploy-state.v1":
            return value
        sources = {
            ".codex-plugin/plugin.json": source,
            "agents/README.md": source,
            "agents/worker.toml": source,
        }
        if schema in {
            "bears-plugin-deploy-state.v4",
            "bears-plugin-deploy-state.v5",
        }:
            sources.update(
                {
                    "role-definitions/capability-catalog.v1.json": source,
                    "role-definitions/worker.json": source,
                }
            )
        generation = "b" * 64
        value.update(
            {
                "role_generation": generation,
                "role_count": 1,
                "role_catalog_sha256": generation,
                "role_receipt_sha256": "f" * 64,
                "role_source_blobs": sources,
                "role_profiles": [
                    {
                        "name": "worker",
                        "config_file": (
                            "/var/lib/bears-plugin-deploy/ai1/role-generations/"
                            f"{generation}/worker.toml"
                        ),
                        "git_oid": source["git_oid"],
                        "sha256": source["sha256"],
                    }
                ],
            }
        )
        if schema in {
            "bears-plugin-deploy-state.v3",
            "bears-plugin-deploy-state.v4",
        }:
            value.update(
                {
                    "graph_template_sha256": "1" * 64,
                    "graph_block_sha256": "2" * 64,
                    "graph_separator_added": False,
                }
            )
        return value

    def test_embedded_installer_accepts_v1_through_v5(self) -> None:
        validate = embedded_installer_validator()["validate_destination_receipt"]
        for number in range(1, 6):
            schema = f"bears-plugin-deploy-state.v{number}"
            receipt = self.receipt(schema)
            self.assertEqual(
                validate(json.dumps(receipt).encode("utf-8")),
                receipt,
            )

    def test_embedded_installer_rejects_graph_fields_on_v5(self) -> None:
        validate = embedded_installer_validator()["validate_destination_receipt"]
        receipt = self.receipt(DEPLOY_RECEIPT_SCHEMA)
        receipt.update(
            {
                "graph_template_sha256": "1" * 64,
                "graph_block_sha256": "2" * 64,
                "graph_separator_added": False,
            }
        )
        with self.assertRaises(SystemExit):
            validate(json.dumps(receipt).encode("utf-8"))


class GatewayRecoveryOutcomeTests(unittest.TestCase):
    def test_gateway_runner_uses_bounded_inherited_lock_lease(self) -> None:
        requested = "a" * 40
        process = mock.Mock()
        process.pid = 12345
        process.returncode = 0
        with (
            mock.patch.object(
                promote_gateway.subprocess,
                "Popen",
                return_value=process,
            ) as popen,
            mock.patch.object(
                promote_gateway,
                "_capture_gateway_output",
                return_value=(b"stdout", b"stderr"),
            ) as capture,
        ):
            result = promote_gateway._run_gateway(requested, b"token\n", 17)

        argv = popen.call_args.args[0]
        kwargs = popen.call_args.kwargs
        self.assertEqual(argv[0], promote_gateway.TIMEOUT)
        self.assertIn(f"{promote_gateway.GATEWAY_TIMEOUT_SECONDS}s", argv)
        self.assertIn("--gateway-child", argv)
        self.assertEqual(argv[-2], "17")
        self.assertEqual(argv[-1], requested)
        self.assertEqual(kwargs["pass_fds"], (17,))
        self.assertTrue(kwargs["start_new_session"])
        capture.assert_called_once_with(
            process,
            b"token\n",
            promote_gateway.GATEWAY_TIMEOUT_SECONDS
            + promote_gateway.GATEWAY_KILL_AFTER_SECONDS
            + promote_gateway.GATEWAY_COMMUNICATE_GRACE_SECONDS,
        )
        self.assertEqual(result.returncode, 0)

    def test_gateway_runner_reaps_group_before_propagating_wait_failure(self) -> None:
        requested = "a" * 40
        expired = subprocess.TimeoutExpired([promote_gateway.TIMEOUT], 1)
        process = mock.Mock()
        process.pid = 12345
        with (
            mock.patch.object(promote_gateway.subprocess, "Popen", return_value=process),
            mock.patch.object(
                promote_gateway,
                "_capture_gateway_output",
                side_effect=expired,
            ),
            mock.patch.object(promote_gateway, "_terminate_gateway_group") as terminate,
            self.assertRaises(subprocess.TimeoutExpired),
        ):
            promote_gateway._run_gateway(requested, b"token\n", 17)

        terminate.assert_called_once_with(process)

    def test_gateway_output_capture_discards_bytes_above_budget(self) -> None:
        script = (
            "import sys; "
            f"sys.stdout.buffer.write(b'x' * {promote_gateway.MAX_GATEWAY_OUTPUT * 4}); "
            f"sys.stderr.buffer.write(b'y' * {promote_gateway.MAX_GATEWAY_OUTPUT * 4})"
        )
        process = subprocess.Popen(
            [promote_gateway.PYTHON, "-c", script],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

        stdout, stderr = promote_gateway._capture_gateway_output(process, b"", 5)

        self.assertEqual(stdout, b"x" * promote_gateway.MAX_GATEWAY_OUTPUT)
        self.assertEqual(stderr, b"y" * promote_gateway.MAX_GATEWAY_OUTPUT)
        self.assertEqual(process.returncode, 0)

    def test_gateway_child_closes_root_lease_before_non_root_exec(self) -> None:
        requested = "a" * 40
        metadata = SimpleNamespace(
            st_mode=0o100600,
            st_dev=1,
            st_ino=2,
            st_uid=0,
            st_gid=0,
        )
        lock_path = mock.Mock()
        lock_path.stat.return_value = metadata
        calls: list[tuple[str, object]] = []

        def close(descriptor: int) -> None:
            calls.append(("close", descriptor))

        def execve(path: str, argv: list[str], env: dict[str, str]) -> None:
            calls.append(("exec", (path, argv, env)))
            raise RuntimeError("exec sentinel")

        with (
            mock.patch.object(promote_gateway, "LOCK_FILE", lock_path),
            mock.patch.object(promote_gateway.os, "fstat", return_value=metadata),
            mock.patch.object(promote_gateway.fcntl, "flock") as flock,
            mock.patch.object(promote_gateway.os, "close", side_effect=close),
            mock.patch.object(promote_gateway.os, "execve", side_effect=execve),
            self.assertRaisesRegex(RuntimeError, "exec sentinel"),
        ):
            promote_gateway._exec_gateway_child("17", requested)

        flock.assert_called_once_with(17, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.assertEqual(calls[0], ("close", 17))
        self.assertEqual(calls[1][0], "exec")
        exec_path, exec_argv, _ = calls[1][1]
        self.assertEqual(exec_path, promote_gateway.RUNUSER)
        self.assertEqual(exec_argv[0], promote_gateway.RUNUSER)
        self.assertNotIn("17", exec_argv)

    @unittest.skipUnless(hasattr(os, "fork"), "requires POSIX fork and flock")
    def test_inherited_lease_survives_parent_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "lease.lock"
            read_descriptor, write_descriptor = os.pipe()
            child = os.fork()
            if child == 0:
                try:
                    os.close(read_descriptor)
                    lease = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
                    fcntl.flock(lease, fcntl.LOCK_EX)
                    supervisor = subprocess.Popen(
                        [promote_gateway.TIMEOUT, "1s", "/usr/bin/sleep", "0.3"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                        pass_fds=(lease,),
                    )
                    if supervisor.pid <= 0:
                        raise AssertionError("timeout supervisor did not start")
                    os.write(write_descriptor, b"1")
                finally:
                    os._exit(0)

            os.close(write_descriptor)
            try:
                self.assertEqual(os.read(read_descriptor, 1), b"1")
                os.waitpid(child, 0)
                contender = os.open(lock_path, os.O_RDWR | os.O_CLOEXEC)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    deadline = time.monotonic() + 2
                    while True:
                        try:
                            fcntl.flock(contender, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            if time.monotonic() >= deadline:
                                self.fail("inherited gateway lease did not expire")
                            time.sleep(0.02)
                finally:
                    os.close(contender)
            finally:
                os.close(read_descriptor)

    def test_durable_requested_recovery_is_a_structured_success(self) -> None:
        with mock.patch.object(
            promotion,
            "converge_promotion_intent",
            return_value="requested",
        ):
            status = promotion.fail_after_recovery(0, {}, RuntimeError("transient"))

        self.assertEqual(status, "recovered-requested")

    def test_private_v5_receipt_binds_requested_sha(self) -> None:
        requested = "a" * 40
        receipt = {
            "schema": DEPLOY_RECEIPT_SCHEMA,
            "repository": promote_gateway.REPOSITORY,
            "marketplace": "bears-app-based-workflow",
            "plugin": "bears-app-based-workflow",
            "sha": requested,
            "version": "0.5.0",
            "payload_fingerprint": "b" * 64,
            "role_generation": "c" * 64,
            "role_count": 1,
            "role_catalog_sha256": "c" * 64,
            "role_receipt_sha256": "d" * 64,
            "role_source_blobs": {},
            "role_profiles": [],
        }
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)
            state_root.chmod(0o700)
            source = {"git_oid": "e" * 40, "sha256": "f" * 64}
            receipt["role_source_blobs"] = {
                ".codex-plugin/plugin.json": source,
                "agents/README.md": source,
                "agents/worker.toml": source,
                "role-definitions/capability-catalog.v1.json": source,
                "role-definitions/worker.json": source,
            }
            receipt["role_profiles"] = [
                {
                    "name": "worker",
                    "config_file": str(
                        state_root / "role-generations" / ("c" * 64) / "worker.toml"
                    ),
                    "git_oid": source["git_oid"],
                    "sha256": source["sha256"],
                }
            ]
            receipt_path = state_root / "bears-app-based-workflow.json"
            receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
            receipt_path.chmod(0o600)
            account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
            with (
                mock.patch.object(promote_gateway, "DEPLOY_STATE_DIR", state_root),
                mock.patch.object(promote_gateway, "DEPLOY_RECEIPT", receipt_path),
                mock.patch.object(promote_gateway.pwd, "getpwnam", return_value=account),
            ):
                self.assertTrue(promote_gateway._durable_v5_binds(requested))
                self.assertFalse(promote_gateway._durable_v5_binds("e" * 40))
                receipt["schema"] = ROLE_GRAPH_DEPLOY_RECEIPT_SCHEMA
                receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
                receipt_path.chmod(0o600)
                self.assertFalse(promote_gateway._durable_v5_binds(requested))

    def test_active_gateway_binding_requires_matching_launcher(self) -> None:
        requested = "a" * 40
        launcher_bytes = b"#!/usr/bin/env python3\n"
        lock_bytes = b"locked requirements\n"
        module_bytes = {
            name: f"# {name}\n".encode("ascii")
            for name in {*promote_gateway.REQUIRED_MODULES, "models.py"}
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            package.mkdir()
            modules = package / "bears_deploy"
            modules.mkdir()
            for name, data in module_bytes.items():
                (modules / name).write_bytes(data)
            (package / ".sentry-requirements.lock").write_bytes(lock_bytes)
            launcher = root / "launcher"
            launcher.write_bytes(launcher_bytes)
            source_receipt = {
                "schema": "bears-plugin-gateway-source.v1",
                "source_sha": requested,
                "launcher_sha256": hashlib.sha256(launcher_bytes).hexdigest(),
                "requirements_sha256": hashlib.sha256(lock_bytes).hexdigest(),
                "modules": {
                    name: hashlib.sha256(data).hexdigest()
                    for name, data in module_bytes.items()
                },
            }
            (package / ".gateway-source.json").write_text(
                json.dumps(source_receipt) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(promote_gateway, "PACKAGE_ROOT", package),
                mock.patch.object(promote_gateway, "LAUNCHER", launcher),
                mock.patch.object(promote_gateway, "_validate_stage"),
                mock.patch.object(promote_gateway, "_validate_installed_file"),
            ):
                self.assertTrue(promote_gateway._active_gateway_binds(requested))
                launcher.write_bytes(b"changed")
                self.assertFalse(promote_gateway._active_gateway_binds(requested))

                launcher.write_bytes(launcher_bytes)
                (package / ".sentry-requirements.lock").write_bytes(b"changed")
                self.assertFalse(promote_gateway._active_gateway_binds(requested))

                (package / ".sentry-requirements.lock").write_bytes(lock_bytes)
                for name, data in module_bytes.items():
                    path = modules / name
                    path.write_bytes(b"changed")
                    self.assertFalse(
                        promote_gateway._active_gateway_binds(requested),
                        msg=f"mutated module was accepted: {name}",
                    )
                    path.write_bytes(data)

                (modules / "rogue.py").write_bytes(b"# unreceipted\n")
                self.assertFalse(promote_gateway._active_gateway_binds(requested))

    def test_active_gateway_binding_rejects_unsafe_module_name(self) -> None:
        requested = "a" * 40
        value = {
            "schema": "bears-plugin-gateway-source.v1",
            "source_sha": requested,
            "launcher_sha256": "b" * 64,
            "requirements_sha256": "c" * 64,
            "modules": {
                **{name: "d" * 64 for name in promote_gateway.REQUIRED_MODULES},
                "../escape.py": "e" * 64,
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "package"
            package.mkdir()
            launcher = root / "launcher"
            launcher.write_bytes(b"launcher")
            (package / ".gateway-source.json").write_text(
                json.dumps(value) + "\n",
                encoding="utf-8",
            )
            with (
                mock.patch.object(promote_gateway, "PACKAGE_ROOT", package),
                mock.patch.object(promote_gateway, "LAUNCHER", launcher),
                mock.patch.object(promote_gateway, "_validate_stage"),
                mock.patch.object(promote_gateway, "_validate_installed_file"),
            ):
                self.assertFalse(promote_gateway._active_gateway_binds(requested))

    def test_failure_retains_only_active_gateway_with_matching_v5_receipt(self) -> None:
        requested = "a" * 40
        with (
            mock.patch.object(promote_gateway, "_active_gateway_binds", return_value=True),
            mock.patch.object(promote_gateway, "_durable_v5_binds", return_value=True),
            mock.patch.object(promote_gateway, "_commit_active_gateway") as commit,
            mock.patch.object(promote_gateway, "_rollback") as rollback,
        ):
            self.assertTrue(promote_gateway._settle_active_gateway_after_failure(requested))
        commit.assert_called_once_with(requested)
        rollback.assert_not_called()

        with (
            mock.patch.object(promote_gateway, "_active_gateway_binds", return_value=False),
            mock.patch.object(promote_gateway, "_durable_v5_binds", return_value=True),
            mock.patch.object(promote_gateway, "_commit_active_gateway") as commit,
            mock.patch.object(promote_gateway, "_rollback") as rollback,
        ):
            self.assertFalse(promote_gateway._settle_active_gateway_after_failure(requested))
        commit.assert_not_called()
        rollback.assert_called_once_with()

    def test_interrupted_root_transaction_uses_receipt_aware_settlement(self) -> None:
        requested = "a" * 40
        journal = {
            "schema": "bears-plugin-gateway-update.v1",
            "sha": requested,
            "state": "activated",
        }
        with tempfile.TemporaryDirectory() as directory:
            journal_path = Path(directory) / "transaction.json"
            journal_path.write_text(json.dumps(journal) + "\n", encoding="utf-8")
            with (
                mock.patch.object(promote_gateway, "JOURNAL_FILE", journal_path),
                mock.patch.object(promote_gateway, "PACKAGE_BACKUP", Path(directory) / "package"),
                mock.patch.object(promote_gateway, "LAUNCHER_BACKUP", Path(directory) / "launcher"),
                mock.patch.object(promote_gateway, "_validate_installed_file"),
                mock.patch.object(
                    promote_gateway,
                    "_settle_active_gateway_after_failure",
                ) as settle,
            ):
                promote_gateway._recover_interrupted_transaction()

        settle.assert_called_once_with(requested)


if __name__ == "__main__":
    unittest.main()
