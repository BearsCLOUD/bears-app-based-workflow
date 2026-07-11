#!/usr/bin/env python3
"""Deterministic authored coverage for the fixed deploy gateway."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import subprocess
import tempfile
import unittest
from unittest import mock

MODULE_PATH = Path(__file__).with_name("deploy_plugin.py")
SPEC = importlib.util.spec_from_file_location("deploy_plugin_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("deploy gateway module is unavailable")
DEPLOY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEPLOY
SPEC.loader.exec_module(DEPLOY)


class StubResponse:
    """Minimal context-managed response used without network access."""

    def __enter__(self) -> "StubResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, _: int) -> bytes:
        return b""


class SentryGatewayCoverage(unittest.TestCase):
    def context(self) -> object:
        context = DEPLOY.DeployContext("a" * 40)
        context.version = "0.1.0+codex.20260711000000"
        return context

    def test_event_is_normalized_and_grouped(self) -> None:
        with mock.patch.dict(
            DEPLOY.os.environ,
            {"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "4"},
            clear=False,
        ):
            event = DEPLOY.sentry_event("post-mutation-failure", self.context())
        self.assertEqual(
            event["fingerprint"],
            [DEPLOY.SENTRY_SERVICE, DEPLOY.SENTRY_COMPONENT, "post-mutation-failure"],
        )
        self.assertEqual(
            set(event["tags"]),
            {
                "error_code",
                "service",
                "component",
                "operation",
                "repository",
                "plugin",
                "git_sha",
                "plugin_version",
                "workflow_run",
                "receipt_schema",
            },
        )
        self.assertEqual(event["tags"]["workflow_run"], "123:4")
        encoded = json.dumps(event)
        for prohibited in ("stdout", "stderr", "request_body", "https://", "locals"):
            self.assertNotIn(prohibited, encoded)

    def test_transport_uses_stub_and_returns_event_reference(self) -> None:
        captured: dict[str, object] = {}

        def opener(outbound: object, *, timeout: int) -> StubResponse:
            captured["outbound"] = outbound
            captured["timeout"] = timeout
            return StubResponse()

        with mock.patch.object(
            DEPLOY,
            "read_sentry_dsn",
            return_value="https://public@example.invalid/42",
        ):
            reference = DEPLOY.report_sentry(
                "mutation-failure-after-start",
                self.context(),
                opener=opener,
            )
        self.assertRegex(reference or "", r"^sentry-event:[0-9a-f]{32}$")
        self.assertEqual(captured["timeout"], DEPLOY.SENTRY_TIMEOUT_SECONDS)
        outbound = captured["outbound"]
        self.assertEqual(outbound.full_url, "https://example.invalid/api/42/envelope/")
        self.assertIn("sentry_key=public", outbound.headers["X-sentry-auth"])

    def test_transport_failure_does_not_escape(self) -> None:
        def opener(*_: object, **__: object) -> StubResponse:
            raise OSError("stub transport failure")

        with mock.patch.object(
            DEPLOY,
            "read_sentry_dsn",
            return_value="https://public@example.invalid/42",
        ):
            reference = DEPLOY.report_sentry(
                "post-mutation-failure",
                self.context(),
                opener=opener,
            )
        self.assertIsNone(reference)


class GitHubCredentialCoverage(unittest.TestCase):
    TOKEN = "ghs_" + "A" * 36

    def test_job_token_pipe_is_single_line_and_bounded(self) -> None:
        self.assertEqual(
            DEPLOY.read_github_token(io.BytesIO((self.TOKEN + "\n").encode())),
            self.TOKEN,
        )
        for invalid in (
            b"",
            b"short\n",
            (self.TOKEN + "\nextra\n").encode(),
            ("A" * (DEPLOY.GITHUB_TOKEN_MAX_BYTES + 1) + "\n").encode(),
            (self.TOKEN + " with-space\n").encode(),
        ):
            with self.subTest(length=len(invalid)):
                with self.assertRaisesRegex(DEPLOY.DeployError, "GitHub job credential"):
                    DEPLOY.read_github_token(io.BytesIO(invalid))

    def test_fetch_uses_url_scoped_header_without_token_in_argv(self) -> None:
        with mock.patch.object(DEPLOY, "run") as runner:
            DEPLOY.fetch_main(Path("/safe/repository.git"), self.TOKEN)
        runner.assert_called_once()
        argv = runner.call_args.args[0]
        environment = runner.call_args.kwargs["env"]
        self.assertNotIn(self.TOKEN, "\0".join(argv))
        self.assertEqual(environment["GIT_CONFIG_COUNT"], "2")
        self.assertEqual(environment["GIT_CONFIG_KEY_0"], "credential.helper")
        self.assertEqual(environment["GIT_CONFIG_VALUE_0"], "")
        self.assertEqual(
            environment["GIT_CONFIG_KEY_1"],
            "http.https://github.com/.extraHeader",
        )
        header = environment["GIT_CONFIG_VALUE_1"]
        self.assertTrue(header.startswith("Authorization: Basic "))
        encoded = header.removeprefix("Authorization: Basic ")
        self.assertEqual(
            DEPLOY.base64.b64decode(encoded).decode(),
            f"x-access-token:{self.TOKEN}",
        )
        self.assertNotIn("GIT_CONFIG_COUNT", DEPLOY.ENV)

    def test_workflow_pipes_ephemeral_job_token_to_gateway(self) -> None:
        workflow = (
            MODULE_PATH.parents[1] / "workflows/plugin-ci-cd.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        self.assertIn(
            "printf '%s\\n' \"$GH_TOKEN\" | sudo -n -u ai1 -- \"$gateway\"",
            workflow,
        )


class StateDirectoryCoverage(unittest.TestCase):
    @staticmethod
    def directory(uid: int, gid: int, mode: int) -> object:
        return mock.Mock(st_mode=stat.S_IFDIR | mode, st_uid=uid, st_gid=gid)

    def test_safe_root_provisioned_path_is_opened_without_creation(self) -> None:
        descriptors = [10, 11, 12, 13, 14]
        metadata = [
            self.directory(0, 0, 0o755),
            self.directory(0, 0, 0o755),
            self.directory(0, 0, 0o755),
            self.directory(0, 0, 0o755),
            self.directory(1000, 1000, 0o700),
        ]
        with (
            mock.patch.object(DEPLOY.os, "open", side_effect=descriptors) as opener,
            mock.patch.object(DEPLOY.os, "fstat", side_effect=metadata),
            mock.patch.object(DEPLOY.os, "close"),
            mock.patch.object(DEPLOY.os, "mkdir") as mkdir,
            mock.patch.object(DEPLOY.os, "geteuid", return_value=1000),
            mock.patch.object(DEPLOY.os, "getegid", return_value=1000),
        ):
            descriptor = DEPLOY.open_state_directory()
        self.assertEqual(descriptor, 14)
        self.assertEqual([call.args[0] for call in opener.call_args_list], ["/", "var", "lib", "bears-plugin-deploy", "ai1"])
        mkdir.assert_not_called()

    def test_missing_root_provision_is_not_created_by_gateway(self) -> None:
        with (
            mock.patch.object(
                DEPLOY.os,
                "open",
                side_effect=[10, 11, 12, FileNotFoundError()],
            ),
            mock.patch.object(
                DEPLOY.os,
                "fstat",
                side_effect=[
                    self.directory(0, 0, 0o755),
                    self.directory(0, 0, 0o755),
                    self.directory(0, 0, 0o755),
                ],
            ),
            mock.patch.object(DEPLOY.os, "close"),
            mock.patch.object(DEPLOY.os, "mkdir") as mkdir,
        ):
            with self.assertRaisesRegex(DEPLOY.DeployError, "root-provisioned"):
                DEPLOY.open_state_directory()
        mkdir.assert_not_called()

    def test_unsafe_new_ancestor_parent_or_leaf_is_rejected(self) -> None:
        cases = (
            (1, self.directory(1000, 0, 0o755)),
            (3, self.directory(0, 0, 0o775)),
            (4, self.directory(1000, 1001, 0o700)),
        )
        baseline = [
            self.directory(0, 0, 0o755),
            self.directory(0, 0, 0o755),
            self.directory(0, 0, 0o755),
            self.directory(0, 0, 0o755),
            self.directory(1000, 1000, 0o700),
        ]
        for index, unsafe in cases:
            with self.subTest(index=index):
                metadata = list(baseline)
                metadata[index] = unsafe
                with (
                    mock.patch.object(DEPLOY.os, "open", side_effect=[10, 11, 12, 13, 14]),
                    mock.patch.object(DEPLOY.os, "fstat", side_effect=metadata),
                    mock.patch.object(DEPLOY.os, "close"),
                    mock.patch.object(DEPLOY.os, "geteuid", return_value=1000),
                    mock.patch.object(DEPLOY.os, "getegid", return_value=1000),
                ):
                    with self.assertRaises(DEPLOY.DeployError):
                        DEPLOY.open_state_directory()


class InstallerStateMigrationCoverage(unittest.TestCase):
    @staticmethod
    def installer_source() -> str:
        return MODULE_PATH.with_name("install-runner.sh").read_text(encoding="utf-8")

    @classmethod
    def importer_source(cls) -> str:
        source = cls.installer_source()
        return source.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]

    def test_reviewed_installer_keeps_old_and_new_path_guards(self) -> None:
        source = self.installer_source()
        for required in (
            'DEPLOY_STATE_ROOT="/var/lib/bears-plugin-deploy"',
            'DEPLOY_STATE_DIR="$DEPLOY_STATE_ROOT/ai1"',
            'LEGACY_DEPLOY_STATE_DIR="/srv/bears/codex/ai1/.local/state/bears-plugin-deploy"',
            'IMPORT_STAGE = f".{PLUGIN}.legacy-state-import.stage"',
            'IMPORT_TOMBSTONE = f"{PLUGIN}.legacy-state-imported.json"',
            'IMPORT_TOMBSTONE_SCHEMA = "bears-plugin-deploy-state-import.v1"',
            "os.O_NOFOLLOW",
            'fail("legacy deployment state has an active promotion intent")',
            'fail("new deployment state is non-empty before one-time receipt import")',
            "RENAME_NOREPLACE",
            "$DEPLOY_STATE_DIR",
        ):
            self.assertIn(required, source)
        self.assertIn('(\"bears\", \"/srv/bears\", 0, AI1_GID, 0o775)', source)
        self.assertIn('(\"codex\", \"/srv/bears/codex\", AI1_UID, None, 0o2770)', source)

    def test_service_cgroup_is_empty_before_import_and_future_stops_are_complete(self) -> None:
        source = self.installer_source()
        main = source[source.index("_install_runner_main() {"):]
        importer = main.index("_install_runner_import_deployment_state")
        for required in (
            '_install_runner_quiesce_managed_service "$SERVICE_NAME" "/sys/fs/cgroup"',
            "grep -qx 'populated 0'",
            'local unit="$1" cgroup_root="$2" cgroup kill_file attempt',
            'kill_file="${cgroup_root%/}${cgroup}/cgroup.kill"',
            '_install_runner_die "$unit service cgroup still has running processes"',
            "KillMode=control-group",
        ):
            self.assertIn(required, source)
        self.assertLess(
            main.index(
                '_install_runner_quiesce_managed_service "$SERVICE_NAME" "/sys/fs/cgroup"'
            ),
            importer,
        )
        self.assertNotIn("pkill -KILL -u ai1", source)

    def test_gateway_and_legacy_locks_fail_closed_without_waiting(self) -> None:
        source = self.importer_source()
        gateway = source.index("gateway_lock_fd = open_private_lock(")
        old_state = source.index("legacy = optional_old_state()")
        for required in (
            "os.O_CREAT | os.O_EXCL",
            "os.fchown(descriptor, AI1_UID, AI1_GID)",
            "os.fchmod(descriptor, 0o600)",
            "validate_private_file(descriptor, label)",
            "fcntl.LOCK_EX | fcntl.LOCK_NB",
            'fail(f"{label} is busy")',
            'acquire_private_lock(gateway_lock_fd, "gateway deployment state lock")',
            'acquire_private_lock(legacy_lock_fd, "legacy deployment state lock")',
        ):
            self.assertIn(required, source)
        self.assertLess(gateway, old_state)
        self.assertLess(source.index("acquire_private_lock(gateway_lock_fd"), old_state)
        self.assertIn("os.fsync(state)\nos.close(gateway_lock_fd)", source)

    def test_first_import_durably_publishes_receipt_then_bound_tombstone(self) -> None:
        source = self.importer_source()
        publication = source[
            source.index("def write_import_stage"):source.index("gateway_lock_fd =")
        ]
        for required in (
            "os.O_CREAT",
            "os.O_EXCL",
            "RENAME_NOREPLACE",
            "os.fsync(target_fd)",
            "os.fsync(directory)",
            "hmac.compare_digest(durable, payload)",
        ):
            self.assertIn(required, publication)
        receipt_publish = source.index(
            "publish_private_no_replace(\n"
            "                    state,\n"
            "                    IMPORT_STAGE,\n"
            "                    RECEIPT,"
        )
        tombstone_publish = source.index(
            "publish_private_no_replace(\n"
            "                state,\n"
            "                IMPORT_STAGE,\n"
            "                IMPORT_TOMBSTONE,"
        )
        self.assertLess(receipt_publish, tombstone_publish)
        for field in (
            '"source_path": source_path',
            '"source_sha256": source_sha256',
            '"source_receipt": source_identity',
            "LEGACY_RECEIPT_PATH, source_sha256, source_identity",
        ):
            self.assertIn(field, source)

    def test_stage_write_crash_rerun_only_recreates_an_exact_source_prefix(self) -> None:
        source = self.importer_source()
        recovery = source[
            source.index("def reconcile_import_stage"):source.index("def write_import_stage")
        ]
        for required in (
            'read_private(directory, stage_name, "legacy state import staging file")',
            "hashlib.sha256(staged).digest()",
            "hashlib.sha256(expected).digest()",
            "len(staged) < len(expected)",
            "staged, expected[: len(staged)]",
            "os.unlink(stage_name, dir_fd=directory)",
            "os.fsync(directory)",
            'fail(f"{label} staging file drifted from the expected first-import state")',
        ):
            self.assertIn(required, recovery)

    def test_receipt_rename_crash_rerun_advances_to_tombstone_stage(self) -> None:
        source = self.importer_source()
        recovery = source[source.index("destination_present = entry_exists(state, RECEIPT)"):]
        stage_choice = recovery.index(
            "expected_stage = expected_tombstone if destination_present else source"
        )
        destination_check = recovery.index("if destination_present:", stage_choice)
        tombstone_publish = recovery.index("IMPORT_TOMBSTONE,", destination_check)
        self.assertLess(stage_choice, destination_check)
        self.assertLess(destination_check, tombstone_publish)

    def test_tombstone_write_crash_rerun_is_idempotent(self) -> None:
        source = self.importer_source()
        publisher = source[
            source.index("def publish_private_no_replace"):source.index("gateway_lock_fd =")
        ]
        for required in (
            "write_import_stage(directory, stage_name, payload, label)",
            "number != errno.EEXIST",
            "hmac.compare_digest(current, payload)",
            "os.unlink(stage_name, dir_fd=directory)",
            "os.fsync(directory)",
        ):
            self.assertIn(required, publisher)
        rerun = source[source.index("if import_tombstone_present:"):]
        self.assertIn("partial_recoverable=False", rerun)
        self.assertIn(
            "publish_private_no_replace(\n"
            "                    state,\n"
            "                    IMPORT_STAGE,\n"
            "                    IMPORT_TOMBSTONE",
            rerun,
        )

    def test_rerun_accepts_bound_tombstone_and_evolved_destination(self) -> None:
        source = self.importer_source()
        rerun = source[source.index("if import_tombstone_present:"):]
        tombstone_check = rerun.index(
            "tombstone, LEGACY_RECEIPT_PATH, source, source_identity"
        )
        destination_check = rerun.index("validate_destination_receipt(destination)")
        self.assertLess(tombstone_check, destination_check)
        validator = source[
            source.index("def validate_destination_receipt"):source.index(
                "def import_tombstone_bytes"
            )
        ]
        self.assertIn("if schema == LEGACY_RECEIPT_SCHEMA:", validator)
        self.assertIn("schema != DEPLOY_RECEIPT_SCHEMA", validator)
        self.assertIn("RECEIPT_FIELDS | ROLE_RECEIPT_FIELDS", validator)

    def test_changed_legacy_source_is_rejected_against_exact_tombstone(self) -> None:
        source = self.importer_source()
        validator = source[
            source.index("def validate_import_tombstone"):source.index(
                "libc = ctypes.CDLL"
            )
        ]
        for required in (
            "set(value) != expected_fields",
            'value.get("source_path") != source_path',
            "source_sha256 = hashlib.sha256(source).hexdigest()",
            'hmac.compare_digest(value["source_sha256"], source_sha256)',
            "tombstone_identity != source_identity",
            'fail("legacy deployment receipt drifted from its import tombstone")',
        ):
            self.assertIn(required, validator)

    def test_bad_or_missing_tombstone_fails_closed(self) -> None:
        source = self.importer_source()
        for required in (
            'fail("legacy state import tombstone shape is invalid")',
            'fail("legacy deployment receipt source is missing after import")',
            'fail("legacy deployment receipt source disappeared after import")',
            'fail("new deployment receipt is missing after legacy state import")',
            '"without an import tombstone"',
        ):
            self.assertIn(required, source)

    def test_conflicting_destination_without_tombstone_is_rejected(self) -> None:
        source = self.importer_source()
        missing_tombstone = source[source.index("            expected_stage ="):]
        compare = missing_tombstone.index("hmac.compare_digest(source, destination)")
        rejection = missing_tombstone.index(
            '"new deployment state conflicts with the legacy receipt "'
        )
        tombstone_publish = missing_tombstone.index(
            "publish_private_no_replace(\n"
            "                state,\n"
            "                IMPORT_STAGE,\n"
            "                IMPORT_TOMBSTONE"
        )
        self.assertLess(compare, rejection)
        self.assertLess(rejection, tombstone_publish)
        self.assertNotIn("os.unlink(RECEIPT, dir_fd=legacy)", source)


class RoleReconciliationCoverage(unittest.TestCase):
    SHA = "a" * 40
    VERSION = "0.1.0+codex.20260711000000"
    FINGERPRINT = "f" * 64
    EXPECTED_NAMES = (
        "app-worker",
        "diagnostic-command-runner",
        "domain-lane-orchestrator",
        "explorer",
        "primary-source-researcher",
        "role-profile-architect",
        "runtime-evidence-reader",
        "security-analysis-critic",
        "wave-change-critic",
        "worker",
        "workflow-orchestrator",
    )

    def test_literal_independent_canonical_role_names(self) -> None:
        self.assertEqual(DEPLOY.CANONICAL_ROLE_NAMES, self.EXPECTED_NAMES)
        self.assertEqual(len(set(self.EXPECTED_NAMES)), 11)

    def role_record(self) -> dict[str, object]:
        generation = "1" * 64
        blobs = {
            relative: {"git_oid": "2" * 40, "sha256": "3" * 64}
            for relative in {".codex-plugin/plugin.json", *DEPLOY.AGENTS_TREE_PATHS}
        }
        return {
            "payload_fingerprint": self.FINGERPRINT,
            "role_generation": generation,
            "role_count": DEPLOY.EXPECTED_ROLE_COUNT,
            "role_catalog_sha256": generation,
            "role_receipt_sha256": "4" * 64,
            "role_source_blobs": blobs,
            "role_profiles": [
                {
                    "name": name,
                    "config_file": str(
                        DEPLOY.ROLE_GENERATIONS_DIR / generation / f"{name}.toml"
                    ),
                    "git_oid": blobs[f"agents/{name}.toml"]["git_oid"],
                    "sha256": blobs[f"agents/{name}.toml"]["sha256"],
                }
                for name in DEPLOY.CANONICAL_ROLE_NAMES
            ],
        }

    def state(self) -> dict[str, object]:
        return {
            "schema": DEPLOY.DEPLOY_RECEIPT_SCHEMA,
            "repository": DEPLOY.REPOSITORY,
            "plugin": DEPLOY.PLUGIN,
            "marketplace": DEPLOY.MARKETPLACE,
            "sha": self.SHA,
            "version": self.VERSION,
            **self.role_record(),
        }

    def legacy_state(self) -> dict[str, object]:
        return {
            "schema": DEPLOY.LEGACY_DEPLOY_RECEIPT_SCHEMA,
            "repository": DEPLOY.REPOSITORY,
            "plugin": DEPLOY.PLUGIN,
            "marketplace": DEPLOY.MARKETPLACE,
            "sha": self.SHA,
            "version": self.VERSION,
            "payload_fingerprint": self.FINGERPRINT,
        }

    def catalog(self, count: int = DEPLOY.EXPECTED_ROLE_COUNT) -> dict[str, str]:
        return {
            name: f"/exact/durable/roles/{name}.toml"
            for name in DEPLOY.CANONICAL_ROLE_NAMES[:count]
        }

    def promotion_patches(self, *, states: list[object]) -> list[object]:
        return [
            mock.patch.object(DEPLOY, "recover_promotion_intent"),
            mock.patch.object(DEPLOY, "prepare_mirror", return_value=self.SHA),
            mock.patch.object(
                DEPLOY,
                "manifest",
                return_value={"name": DEPLOY.PLUGIN, "version": self.VERSION},
            ),
            mock.patch.object(DEPLOY, "validate_marketplace"),
            mock.patch.object(DEPLOY, "load_state", side_effect=states),
            mock.patch.object(DEPLOY, "verify_disabled"),
            mock.patch.object(DEPLOY, "save_intent", return_value={}),
            mock.patch.object(DEPLOY, "marketplace_row", return_value={}),
            mock.patch.object(DEPLOY, "run_json", return_value={}),
            mock.patch.object(DEPLOY, "exact_remote"),
            mock.patch.object(DEPLOY, "git_text", return_value=self.SHA),
            mock.patch.object(DEPLOY, "verify_receipted_install"),
            mock.patch.object(DEPLOY, "clear_intent"),
        ]

    def test_new_deploy_reconciles_roles_before_receipt(self) -> None:
        events: list[str] = []
        durable = self.state()
        role_record = self.role_record()
        patches = self.promotion_patches(states=[None, durable])
        patches.extend(
            [
                mock.patch.object(
                    DEPLOY,
                    "reconcile_roles",
                    side_effect=lambda *_: events.append("roles") or role_record,
                ),
                mock.patch.object(
                    DEPLOY,
                    "save_state",
                    side_effect=lambda *_: events.append("receipt"),
                ),
            ]
        )
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            status = DEPLOY.promote(self.SHA, DEPLOY.DeployContext(self.SHA), 7)
        self.assertEqual(status, "deployed")
        self.assertEqual(events, ["roles", "receipt"])

    def test_already_deployed_path_repairs_roles(self) -> None:
        state = self.legacy_state()
        durable = self.state()
        intent: dict[str, object] = {}
        with (
            mock.patch.object(DEPLOY, "recover_promotion_intent"),
            mock.patch.object(DEPLOY, "prepare_mirror", return_value=self.SHA),
            mock.patch.object(DEPLOY, "manifest", return_value={"version": self.VERSION}),
            mock.patch.object(DEPLOY, "validate_marketplace"),
            mock.patch.object(DEPLOY, "load_state", side_effect=[state, durable]),
            mock.patch.object(DEPLOY, "is_ancestor", return_value=True),
            mock.patch.object(DEPLOY, "verify_receipted_install"),
            mock.patch.object(DEPLOY, "save_intent", return_value=intent),
            mock.patch.object(
                DEPLOY,
                "reconcile_receipted_roles",
                return_value=self.role_record(),
            ) as reconcile,
            mock.patch.object(DEPLOY, "save_state"),
            mock.patch.object(DEPLOY, "clear_intent"),
        ):
            status = DEPLOY.promote(self.SHA, DEPLOY.DeployContext(self.SHA), 7)
        self.assertEqual(status, "already-deployed")
        reconcile.assert_called_once_with(7, state, intent)

    def test_older_ancestor_path_repairs_current_roles(self) -> None:
        requested = "b" * 40
        state = self.legacy_state()
        durable = self.state()
        intent: dict[str, object] = {}
        with (
            mock.patch.object(DEPLOY, "recover_promotion_intent"),
            mock.patch.object(DEPLOY, "prepare_mirror", return_value=self.SHA),
            mock.patch.object(DEPLOY, "manifest", return_value={"version": self.VERSION}),
            mock.patch.object(DEPLOY, "validate_marketplace"),
            mock.patch.object(DEPLOY, "load_state", side_effect=[state, durable]),
            mock.patch.object(DEPLOY, "is_ancestor", side_effect=[True, True]),
            mock.patch.object(DEPLOY, "verify_receipted_install"),
            mock.patch.object(DEPLOY, "save_intent", return_value=intent),
            mock.patch.object(
                DEPLOY,
                "reconcile_receipted_roles",
                return_value=self.role_record(),
            ) as reconcile,
            mock.patch.object(DEPLOY, "save_state"),
            mock.patch.object(DEPLOY, "clear_intent"),
        ):
            status = DEPLOY.promote(requested, DEPLOY.DeployContext(requested), 7)
        self.assertEqual(status, "skipped-older-ancestor")
        reconcile.assert_called_once_with(7, state, intent)

    def test_reconciliation_failure_never_saves_new_receipt(self) -> None:
        patches = self.promotion_patches(states=[None])
        reconcile = mock.patch.object(
            DEPLOY,
            "reconcile_roles",
            side_effect=DEPLOY.DeployError("role data rejected"),
        )
        save = mock.patch.object(DEPLOY, "save_state")
        recover = mock.patch.object(
            DEPLOY,
            "fail_after_recovery",
            side_effect=DEPLOY.DeployError("recovery complete"),
        )
        with ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            stack.enter_context(reconcile)
            save_state = stack.enter_context(save)
            stack.enter_context(recover)
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.promote(self.SHA, DEPLOY.DeployContext(self.SHA), 7)
        save_state.assert_not_called()

    def test_malformed_or_owned_collision_fails_closed(self) -> None:
        catalog = self.catalog()
        with self.assertRaises(DEPLOY.DeployError):
            DEPLOY.parse_config(b"[broken", "stub config")
        with self.assertRaises(DEPLOY.DeployError):
            DEPLOY.desired_role_config(
                b'[agents.worker]\nconfig_file = "/tmp/unowned-worker.toml"\n',
                self.VERSION,
                catalog,
            )

    def test_unrelated_global_agents_are_preserved_byte_for_byte(self) -> None:
        original = (
            b'[features]\nexample = true\n\n'
            b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n'
        )
        desired = DEPLOY.desired_role_config(original, self.VERSION, self.catalog())
        outside, span = DEPLOY.config_without_owned_roles(desired)
        self.assertEqual(outside, original)
        self.assertIsNotNone(span)
        parsed = DEPLOY.parse_config(desired, "preserved config")
        self.assertEqual(parsed["agents"]["personal"], {"config_file": "/opt/personal.toml"})
        self.assertEqual(set(parsed["agents"]).intersection(self.EXPECTED_NAMES), set(self.EXPECTED_NAMES))

    def test_exact_live_v1_is_registration_only_and_migrates_to_v2(self) -> None:
        block = DEPLOY.legacy_role_block()
        config = b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n\n' + block
        receipt_bytes = DEPLOY.legacy_role_receipt_bytes()
        self.assertEqual(len(block), 1301)
        self.assertEqual(hashlib.sha256(block).hexdigest(), DEPLOY.LEGACY_ROLE_MANAGED_DIGEST)
        with tempfile.TemporaryDirectory() as temporary:
            receipt_path = Path(temporary) / "receipt.json"
            receipt_path.write_bytes(receipt_bytes)
            receipt_path.chmod(0o600)
            snapshot = (receipt_bytes, receipt_path.stat())
            with mock.patch.object(
                DEPLOY,
                "read_regular_bytes",
                side_effect=AssertionError("legacy profile bytes must not be read"),
            ):
                previous = DEPLOY.validate_owned_role_state(config, snapshot)
        self.assertEqual(previous, DEPLOY.legacy_role_receipt_value())
        current_catalog = self.catalog()
        desired = DEPLOY.desired_role_config(config, self.VERSION, current_catalog)
        DEPLOY.verify_role_config(desired, current_catalog)
        bundle = {
            "profiles": {name: {"sha256": "a" * 64} for name in self.EXPECTED_NAMES}
        }
        current_block = DEPLOY.role_block(self.VERSION, current_catalog)
        migrated = json.loads(
            DEPLOY.build_role_receipt(
                self.VERSION,
                current_block,
                current_catalog,
                bundle,
                previous,
                added_joiner=False,
            )
        )
        self.assertEqual(migrated["schema"], DEPLOY.ROLE_RECEIPT_SCHEMA)
        self.assertEqual(migrated["role_count"], 11)
        self.assertEqual(
            [row["name"] for row in migrated["managed_profiles"]],
            list(self.EXPECTED_NAMES),
        )
        self.assertEqual(migrated["archives"], DEPLOY.legacy_role_receipt_value()["archives"])

    def test_every_v1_fingerprint_drift_fails_without_profile_access(self) -> None:
        block = DEPLOY.legacy_role_block()
        config = b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n\n' + block
        receipt = DEPLOY.legacy_role_receipt_bytes()

        def encoded(change: object) -> bytes:
            value = DEPLOY.legacy_role_receipt_value()
            change(value)
            return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()

        wrong_path = block.replace(
            DEPLOY.LEGACY_ROLE_PATHS["worker"].encode(),
            b"/hostile/legacy/worker.toml",
            1,
        )
        duplicate = b'{"schema":"duplicate",' + receipt[1:]
        cases = {
            "version": (
                config,
                encoded(lambda value: value.__setitem__("version", "0.1.0+codex.20260711074120")),
            ),
            "digest": (
                config,
                encoded(lambda value: value.__setitem__("managed_digest", "0" * 64)),
            ),
            "key": (
                config,
                encoded(lambda value: value.__setitem__("unexpected", True)),
            ),
            "path": (config[: -len(block)] + wrong_path, receipt),
            "length": (config[:-1], receipt),
            "archive": (
                config,
                encoded(lambda value: value["archives"][0].__setitem__("count", 18)),
            ),
            "profile-field": (
                config,
                encoded(lambda value: value.__setitem__("managed_profiles", [])),
            ),
            "duplicate-json": (config, duplicate),
        }
        with tempfile.TemporaryDirectory() as temporary:
            receipt_path = Path(temporary) / "receipt.json"
            for label, (candidate_config, candidate_receipt) in cases.items():
                with self.subTest(label=label):
                    receipt_path.write_bytes(candidate_receipt)
                    receipt_path.chmod(0o600)
                    original_config = bytes(candidate_config)
                    original_receipt = bytes(candidate_receipt)
                    with (
                        mock.patch.object(
                            DEPLOY,
                            "read_regular_bytes",
                            side_effect=AssertionError("legacy profile bytes must not be read"),
                        ),
                        self.assertRaises(DEPLOY.DeployError),
                    ):
                        DEPLOY.validate_owned_role_state(
                            candidate_config,
                            (candidate_receipt, receipt_path.stat()),
                        )
                    self.assertEqual(candidate_config, original_config)
                    self.assertEqual(candidate_receipt, original_receipt)

    def test_missing_or_symlink_role_data_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.read_regular_bytes(root / "missing.toml", "stub role", 1024)
            target = root / "target.toml"
            target.write_text('name = "target"\n', encoding="utf-8")
            link = root / "linked.toml"
            link.symlink_to(target)
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.read_regular_bytes(link, "stub role", 1024)

    def test_wrong_role_count_or_config_path_is_rejected(self) -> None:
        short_catalog = self.catalog(DEPLOY.EXPECTED_ROLE_COUNT - 1)
        with self.assertRaises(DEPLOY.DeployError):
            DEPLOY.verify_role_config(DEPLOY.role_block(self.VERSION, short_catalog), short_catalog)
        catalog = self.catalog()
        wrong = DEPLOY.role_block(self.VERSION, catalog).replace(
            next(iter(catalog.values())).encode(),
            b"/wrong/cache/profile.toml",
            1,
        )
        with self.assertRaises(DEPLOY.DeployError):
            DEPLOY.verify_role_config(wrong, catalog)

    def test_cached_role_bytes_must_match_the_pinned_git_blob(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            profile = repo / "agents/worker.toml"
            profile.parent.mkdir()
            profile.write_text('name = "worker"\n', encoding="utf-8")
            with mock.patch.object(
                DEPLOY,
                "git_text",
                side_effect=[f"100644 blob {'0' * 40}", "sha1"],
            ):
                with self.assertRaises(DEPLOY.DeployError):
                    DEPLOY.verified_git_blob(repo, self.SHA, "agents/worker.toml", 1024)

    def test_atomic_managed_block_publish_preserves_private_mode(self) -> None:
        catalog = self.catalog()
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            home.chmod(0o700)
            config = home / "config.toml"
            config.write_text('[features]\nexample = true\n', encoding="utf-8")
            config.chmod(0o600)
            with mock.patch.object(DEPLOY, "CODEX_HOME", home):
                home_fd, lock_fd = DEPLOY.open_role_config_lock()
                try:
                    before = DEPLOY.read_config_at(home_fd)
                    self.assertIsNotNone(before)
                    desired = DEPLOY.desired_role_config(before[0], self.VERSION, catalog)
                    published = DEPLOY.atomic_config_replace(home_fd, before, desired)
                finally:
                    os.close(lock_fd)
                    os.close(home_fd)
            DEPLOY.verify_role_config(published[0], catalog)
            self.assertEqual(config.stat().st_mode & 0o777, 0o600)

    def test_publication_time_cas_restores_config_and_receipt_races(self) -> None:
        def race_once(real: object, target_name: str, racer_bytes: bytes):
            raced = False

            def operation(directory: int, source: str, target: str, flags: int) -> None:
                nonlocal raced
                if not raced and target == target_name:
                    raced = True
                    racer = f".{target_name}.racer"
                    descriptor = os.open(
                        racer,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC,
                        0o600,
                        dir_fd=directory,
                    )
                    try:
                        os.write(descriptor, racer_bytes)
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
                    os.rename(racer, target, src_dir_fd=directory, dst_dir_fd=directory)
                    os.fsync(directory)
                real(directory, source, target, flags)

            return operation

        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            home.chmod(0o700)
            config = home / "config.toml"
            config.write_bytes(b"before-config\n")
            config.chmod(0o600)
            home_fd = os.open(home, os.O_RDONLY | os.O_DIRECTORY)
            try:
                before = DEPLOY.read_config_at(home_fd)
                with mock.patch.object(
                    DEPLOY,
                    "renameat2",
                    side_effect=race_once(DEPLOY.renameat2, "config.toml", b"racer-config\n"),
                ):
                    with self.assertRaises(DEPLOY.DeployError):
                        DEPLOY.atomic_config_replace(home_fd, before, b"replacement-config\n")
                self.assertEqual(config.read_bytes(), b"racer-config\n")

                state = home / "state"
                state.mkdir(mode=0o700)
                receipt_path = state / DEPLOY.ROLE_RECEIPT_FILE.name
                receipt_path.write_bytes(b"before-receipt\n")
                receipt_path.chmod(0o600)
                state_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    receipt_before = DEPLOY.read_role_receipt_at(state_fd)
                    with mock.patch.object(
                        DEPLOY,
                        "renameat2",
                        side_effect=race_once(
                            DEPLOY.renameat2,
                            DEPLOY.ROLE_RECEIPT_FILE.name,
                            b"racer-receipt\n",
                        ),
                    ):
                        with self.assertRaises(DEPLOY.DeployError):
                            DEPLOY.atomic_role_receipt_replace(
                                state_fd, receipt_before, b"replacement-receipt\n"
                            )
                    self.assertEqual(receipt_path.read_bytes(), b"racer-receipt\n")
                finally:
                    os.close(state_fd)
            finally:
                os.close(home_fd)


class PinnedBundleCoverage(unittest.TestCase):
    VERSION = "0.1.0+codex.20260711000000"

    class SimulatedCrash(BaseException):
        pass

    def git(self, repo: Path, *arguments: str) -> str:
        return subprocess.run(
            ["git", *arguments],
            cwd=repo,
            check=True,
            stdout=subprocess.PIPE,
            text=True,
        ).stdout.strip()

    def repository(self, root: Path, *, payload_marker: Path | None = None) -> tuple[Path, str]:
        repo = root / "repo"
        repo.mkdir()
        self.git(repo, "init", "-q")
        self.git(repo, "config", "user.name", "Bundle Test")
        self.git(repo, "config", "user.email", "bundle@example.invalid")
        manifest = repo / ".codex-plugin/plugin.json"
        manifest.parent.mkdir()
        manifest.write_text(
            json.dumps(
                {
                    "name": DEPLOY.PLUGIN,
                    "repository": DEPLOY.REPOSITORY.removesuffix(".git"),
                    "version": self.VERSION,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        marketplace = repo / ".agents/plugins/marketplace.json"
        marketplace.parent.mkdir(parents=True)
        marketplace.write_text(
            json.dumps(
                {
                    "name": DEPLOY.MARKETPLACE,
                    "plugins": [
                        {
                            "name": DEPLOY.PLUGIN,
                            "source": {"source": "local", "path": "."},
                        }
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        agents = repo / "agents"
        agents.mkdir()
        (agents / "README.md").write_text("# Exact role catalog\n", encoding="utf-8")
        for name in DEPLOY.CANONICAL_ROLE_NAMES:
            (agents / f"{name}.toml").write_text(
                "\n".join(
                    (
                        f'name = "{name}"',
                        'description = "Bounded test role."',
                        'model = "gpt-5.2"',
                        'model_reasoning_effort = "high"',
                        'sandbox_mode = "danger-full-access"',
                        'developer_instructions = "Return a bounded result."',
                        "",
                    )
                ),
                encoding="utf-8",
            )
        if payload_marker is not None:
            self.assertTrue(payload_marker.is_absolute())
            installer = repo / "install"
            installer.write_text(
                "#!/usr/bin/env python3\n"
                "from pathlib import Path\n"
                f"Path({str(payload_marker)!r}).write_text('executed', encoding='utf-8')\n"
                "raise RuntimeError('hostile payload install executed')\n",
                encoding="utf-8",
            )
            installer.chmod(0o755)
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-qm", "fixture")
        self.git(repo, "remote", "add", "origin", DEPLOY.REPOSITORY)
        return repo, self.git(repo, "rev-parse", "HEAD")

    def clone_fixture(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "-q", str(source), str(destination)],
            check=True,
            stdout=subprocess.PIPE,
        )
        self.git(destination, "remote", "set-url", "origin", DEPLOY.REPOSITORY)

    def recommit(self, repo: Path, message: str) -> str:
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", message)
        return self.git(repo, "rev-parse", "HEAD")

    def test_malformed_tree_mode_and_oid_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self.repository(Path(temporary))
            (repo / "agents/extra.toml").write_text('name = "extra"\n', encoding="utf-8")
            sha = self.recommit(repo, "extra tree member")
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.pinned_role_bundle(repo, sha, self.VERSION)
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self.repository(Path(temporary))
            (repo / "agents/worker.toml").chmod(0o755)
            sha = self.recommit(repo, "executable profile")
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.pinned_role_bundle(repo, sha, self.VERSION)
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            profile = repo / "agents/worker.toml"
            profile.parent.mkdir()
            profile.write_text('name = "worker"\n', encoding="utf-8")
            with mock.patch.object(
                DEPLOY,
                "git_text",
                side_effect=["100644 blob not-an-object-id", "sha1"],
            ):
                with self.assertRaises(DEPLOY.DeployError):
                    DEPLOY.verified_git_blob_record(repo, "a" * 40, "agents/worker.toml", 1024)

    def test_manifest_and_profile_schema_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self.repository(Path(temporary))
            (repo / ".codex-plugin/plugin.json").write_text(
                json.dumps({"name": "wrong-plugin", "version": self.VERSION}) + "\n",
                encoding="utf-8",
            )
            sha = self.recommit(repo, "wrong manifest")
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.pinned_role_bundle(repo, sha, self.VERSION)
        with tempfile.TemporaryDirectory() as temporary:
            repo, _ = self.repository(Path(temporary))
            profile = repo / "agents/worker.toml"
            profile.write_text('name = "worker"\ndescription = "incomplete"\n', encoding="utf-8")
            sha = self.recommit(repo, "incomplete profile")
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.pinned_role_bundle(repo, sha, self.VERSION)

    def test_committed_reconciliation_recovery_preserves_pair_and_finalizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, sha = self.repository(root)
            home, state_fd, _, _, _ = RemovalRecoveryCoverage().environment(root)
            legacy_state = RoleReconciliationCoverage().legacy_state()
            legacy_state["sha"] = sha
            state_path = root / "deploy-state" / DEPLOY.STATE_FILE.name
            state_path.write_text(
                json.dumps(legacy_state, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            state_path.chmod(0o600)
            role_generations = state_path.parent / "role-generations"
            role_generations_patch = mock.patch.object(
                DEPLOY,
                "ROLE_GENERATIONS_DIR",
                role_generations,
            )

            def crash_before_finalize(_: object) -> None:
                raise self.SimulatedCrash()

            try:
                role_generations_patch.start()
                intent = DEPLOY.save_intent(state_fd, sha, legacy_state)
                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "plugin_cache", return_value=repo),
                    mock.patch.object(
                        DEPLOY,
                        "verify_install",
                        return_value=RoleReconciliationCoverage.FINGERPRINT,
                    ),
                    mock.patch.object(
                        DEPLOY,
                        "finalize_publication",
                        side_effect=crash_before_finalize,
                    ),
                ):
                    with self.assertRaises(self.SimulatedCrash):
                        DEPLOY.reconcile_roles(sha, self.VERSION, state_fd, intent)

                durable = DEPLOY.load_intent(state_fd)
                self.assertIsNotNone(durable)
                transaction = durable["role_transaction"]
                self.assertEqual(transaction["phase"], "committed")
                materialized = role_generations / transaction["role_generation"]
                self.assertEqual(
                    {path.name for path in materialized.iterdir()},
                    {f"{name}.toml" for name in DEPLOY.CANONICAL_ROLE_NAMES},
                )
                self.assertEqual(
                    {
                        Path(row["config_file"]).parent
                        for row in transaction["role_record"]["role_profiles"]
                    },
                    {materialized},
                )
                config_exchange = home / transaction["config_exchange_name"]
                receipt_exchange = (
                    home / "state" / transaction["receipt_exchange_name"]
                )
                self.assertTrue(config_exchange.exists())
                self.assertTrue(receipt_exchange.exists())
                desired_config = (home / "config.toml").read_bytes()
                receipt_path = home / "state" / DEPLOY.ROLE_RECEIPT_FILE.name
                desired_receipt = receipt_path.read_bytes()

                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "plugin_cache", return_value=repo),
                    mock.patch.object(
                        DEPLOY,
                        "verify_install",
                        return_value=RoleReconciliationCoverage.FINGERPRINT,
                    ),
                ):
                    DEPLOY.recover_promotion_intent(state_fd)
                    DEPLOY.recover_promotion_intent(state_fd)

                self.assertEqual((home / "config.toml").read_bytes(), desired_config)
                self.assertEqual(receipt_path.read_bytes(), desired_receipt)
                self.assertFalse(config_exchange.exists())
                self.assertFalse(receipt_exchange.exists())
                self.assertIsNone(DEPLOY.load_intent(state_fd))
                recovered_state = DEPLOY.load_state(state_fd)
                self.assertIsNotNone(recovered_state)
                self.assertEqual(recovered_state["schema"], DEPLOY.DEPLOY_RECEIPT_SCHEMA)
            finally:
                role_generations_patch.stop()
                os.close(state_fd)

    def test_payload_installer_is_data_and_symlink_swap_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "hostile-install-executed"
            repo, sha = self.repository(root, payload_marker=marker)
            home = root / "codex-home"
            home.mkdir(mode=0o700)
            cache = (
                home
                / "plugins/cache"
                / DEPLOY.MARKETPLACE
                / DEPLOY.PLUGIN
                / self.VERSION
            )
            marketplace_root = root / "marketplace"
            self.clone_fixture(repo, cache)
            self.clone_fixture(repo, marketplace_root)
            state = root / "deploy-state"
            state.mkdir(mode=0o700)
            state_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
            installed = {
                "pluginId": f"{DEPLOY.PLUGIN}@{DEPLOY.MARKETPLACE}",
                "marketplaceSource": DEPLOY.FIXED_MARKETPLACE_SOURCE,
                "installed": True,
                "enabled": True,
                "version": self.VERSION,
            }
            try:
                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "MIRROR", repo),
                    mock.patch.object(DEPLOY, "MARKETPLACE_ROOT", marketplace_root),
                    mock.patch.object(
                        DEPLOY,
                        "ROLE_GENERATIONS_DIR",
                        state / "role-generations",
                    ),
                    mock.patch.object(DEPLOY, "prepare_mirror", return_value=sha),
                    mock.patch.object(DEPLOY, "verify_disabled"),
                    mock.patch.object(DEPLOY, "marketplace_row", return_value={}),
                    mock.patch.object(DEPLOY, "run_json", return_value={}),
                    mock.patch.object(DEPLOY, "plugin_rows", return_value=[installed]),
                ):
                    status = DEPLOY.promote(
                        sha,
                        DEPLOY.DeployContext(sha),
                        state_fd,
                    )
                    durable = DEPLOY.load_state(state_fd)
                self.assertEqual(status, "deployed")
                self.assertIsNotNone(durable)
                self.assertFalse(marker.exists())
                self.assertTrue((home / "config.toml").is_file())
                self.assertTrue(
                    (home / "state" / DEPLOY.ROLE_RECEIPT_FILE.name).is_file()
                )
            finally:
                os.close(state_fd)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repo, sha = self.repository(root)
            outside = root / "outside-worker.toml"
            worker = repo / "agents/worker.toml"
            outside.write_bytes(worker.read_bytes())
            worker.unlink()
            worker.symlink_to(outside)
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.pinned_role_bundle(repo, sha, self.VERSION)


class RemovalRecoveryCoverage(unittest.TestCase):
    SHA = "a" * 40
    VERSION = "0.1.0+codex.20260711000000"

    class SimulatedCrash(BaseException):
        pass

    def environment(self, root: Path) -> tuple[Path, int, dict[str, object], bytes, bytes]:
        home = root / "codex-home"
        home.mkdir(mode=0o700)
        profiles = root / "profiles"
        profiles.mkdir(mode=0o700)
        catalog: dict[str, str] = {}
        records: list[dict[str, str]] = []
        for name in DEPLOY.CANONICAL_ROLE_NAMES:
            path = profiles / f"{name}.toml"
            data = f'name = "{name}"\n'.encode()
            path.write_bytes(data)
            path.chmod(0o600)
            catalog[name] = str(path)
            records.append(
                {
                    "name": name,
                    "config_file": str(path),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )
        block = DEPLOY.role_block(self.VERSION, catalog)
        original = b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n\n' + block
        config = home / "config.toml"
        config.write_bytes(original)
        config.chmod(0o600)
        receipt_value = {
            "schema": DEPLOY.ROLE_RECEIPT_SCHEMA,
            "plugin": DEPLOY.PLUGIN,
            "version": self.VERSION,
            "status": "installed",
            "changed": True,
            "role_count": 11,
            "managed_digest": hashlib.sha256(block).hexdigest(),
            "managed_joiner_added": False,
            "managed_profiles": records,
            "archives": [],
        }
        receipt = (json.dumps(receipt_value, sort_keys=True) + "\n").encode()
        receipt_dir = home / "state"
        receipt_dir.mkdir(mode=0o700)
        receipt_path = receipt_dir / DEPLOY.ROLE_RECEIPT_FILE.name
        receipt_path.write_bytes(receipt)
        receipt_path.chmod(0o600)
        deploy_state = root / "deploy-state"
        deploy_state.mkdir(mode=0o700)
        state_fd = os.open(deploy_state, os.O_RDONLY | os.O_DIRECTORY)
        intent = DEPLOY.save_intent(state_fd, self.SHA, None)
        return home, state_fd, intent, original, receipt

    def assert_removed(self, home: Path) -> None:
        config = (home / "config.toml").read_bytes()
        outside, span = DEPLOY.config_without_owned_roles(config)
        self.assertIsNone(span)
        self.assertIn(b"[agents.personal]", outside)
        receipt = json.loads((home / "state" / DEPLOY.ROLE_RECEIPT_FILE.name).read_bytes())
        self.assertEqual(receipt["schema"], DEPLOY.ROLE_RECEIPT_SCHEMA)
        self.assertEqual(receipt["status"], "uninstalled")

    def test_crash_after_config_publish_recovers_combined_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, state_fd, intent, _, _ = self.environment(Path(temporary))
            calls = 0
            real_publish = DEPLOY.publish_journaled_file

            def crash_before_receipt(*args: object, **kwargs: object) -> object:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise self.SimulatedCrash()
                return real_publish(*args, **kwargs)

            try:
                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "publish_journaled_file", side_effect=crash_before_receipt),
                ):
                    with self.assertRaises(self.SimulatedCrash):
                        DEPLOY.clear_owned_roles(state_fd, intent)
                durable = DEPLOY.load_intent(state_fd)
                with mock.patch.object(DEPLOY, "CODEX_HOME", home):
                    DEPLOY.clear_owned_roles(state_fd, durable)
                self.assert_removed(home)
            finally:
                os.close(state_fd)

    def test_committed_removal_recovery_preserves_pair_and_finalizes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, state_fd, intent, _, _ = self.environment(Path(temporary))

            def crash_before_finalize(_: object) -> None:
                raise self.SimulatedCrash()

            try:
                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(
                        DEPLOY,
                        "finalize_publication",
                        side_effect=crash_before_finalize,
                    ),
                ):
                    with self.assertRaises(self.SimulatedCrash):
                        DEPLOY.clear_owned_roles(state_fd, intent)
                durable = DEPLOY.load_intent(state_fd)
                self.assertIsNotNone(durable)
                transaction = durable["role_transaction"]
                self.assertEqual(transaction["phase"], "committed")
                config_exchange = home / transaction["config_exchange_name"]
                receipt_exchange = (
                    home / "state" / transaction["receipt_exchange_name"]
                )
                self.assertTrue(config_exchange.exists())
                self.assertTrue(receipt_exchange.exists())
                desired_config = (home / "config.toml").read_bytes()
                receipt_path = home / "state" / DEPLOY.ROLE_RECEIPT_FILE.name
                desired_receipt = receipt_path.read_bytes()
                self.assert_removed(home)

                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "run_json", return_value={}),
                    mock.patch.object(DEPLOY, "verify_disabled"),
                ):
                    DEPLOY.recover_promotion_intent(state_fd)
                    DEPLOY.recover_promotion_intent(state_fd)

                self.assertEqual((home / "config.toml").read_bytes(), desired_config)
                self.assertEqual(receipt_path.read_bytes(), desired_receipt)
                self.assertFalse(config_exchange.exists())
                self.assertFalse(receipt_exchange.exists())
                self.assertIsNone(DEPLOY.load_intent(state_fd))
                self.assertIsNone(DEPLOY.load_state(state_fd))
                self.assert_removed(home)
            finally:
                os.close(state_fd)

    def test_journaled_removal_partial_failure_rolls_back_both_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, state_fd, intent, original, receipt = self.environment(Path(temporary))
            calls = 0
            real_publish = DEPLOY.publish_journaled_file

            def fail_receipt(*args: object, **kwargs: object) -> object:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise DEPLOY.DeployError("injected receipt failure")
                return real_publish(*args, **kwargs)

            try:
                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "publish_journaled_file", side_effect=fail_receipt),
                ):
                    with self.assertRaises(DEPLOY.DeployError):
                        DEPLOY.clear_owned_roles(state_fd, intent)
                self.assertEqual((home / "config.toml").read_bytes(), original)
                self.assertEqual(
                    (home / "state" / DEPLOY.ROLE_RECEIPT_FILE.name).read_bytes(), receipt
                )
            finally:
                os.close(state_fd)

    def test_committed_removal_recovers_after_deployment_state_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home, state_fd, intent, _, _ = self.environment(Path(temporary))
            try:
                with mock.patch.object(DEPLOY, "CODEX_HOME", home):
                    committed = DEPLOY.clear_owned_roles(state_fd, intent)
                record = RoleReconciliationCoverage().role_record()
                DEPLOY.save_state(state_fd, self.SHA, self.VERSION, record)
                self.assertIsNotNone(DEPLOY.load_state(state_fd))
                with (
                    mock.patch.object(DEPLOY, "CODEX_HOME", home),
                    mock.patch.object(DEPLOY, "run_json", return_value={}),
                    mock.patch.object(DEPLOY, "verify_disabled"),
                ):
                    outcome = DEPLOY.converge_promotion_intent(state_fd, committed)
                self.assertEqual(outcome, "disabled")
                self.assertIsNone(DEPLOY.load_state(state_fd))
                self.assertIsNone(DEPLOY.load_intent(state_fd))
            finally:
                os.close(state_fd)


class RegistrationMigrationRecoveryCoverage(unittest.TestCase):
    """Exercise every durable boundary in the one-shot v1 registration migration."""

    class SimulatedCrash(BaseException):
        pass

    def environment(self, root: Path) -> tuple[Path, Path, str, int, dict[str, object]]:
        repo, sha = PinnedBundleCoverage().repository(root)
        home = root / "codex-home"
        home.mkdir(mode=0o700)
        config = home / "config.toml"
        config.write_bytes(
            b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n\n'
            + DEPLOY.legacy_role_block()
        )
        config.chmod(0o600)
        receipt_directory = home / "state"
        receipt_directory.mkdir(mode=0o700)
        receipt = receipt_directory / DEPLOY.ROLE_RECEIPT_FILE.name
        receipt.write_bytes(DEPLOY.legacy_role_receipt_bytes())
        receipt.chmod(0o600)
        deploy_state = root / "deploy-state"
        deploy_state.mkdir(mode=0o700)
        state_fd = os.open(deploy_state, os.O_RDONLY | os.O_DIRECTORY)
        intent = DEPLOY.save_intent(state_fd, sha, None)
        return home, repo, sha, state_fd, intent

    def gateway_context(
        self,
        stack: ExitStack,
        home: Path,
        repo: Path,
        deploy_state: Path,
    ) -> None:
        stack.enter_context(mock.patch.object(DEPLOY, "CODEX_HOME", home))
        stack.enter_context(mock.patch.object(DEPLOY, "plugin_cache", return_value=repo))
        stack.enter_context(
            mock.patch.object(
                DEPLOY,
                "ROLE_GENERATIONS_DIR",
                deploy_state / "role-generations",
            )
        )
        stack.enter_context(
            mock.patch.object(
                DEPLOY,
                "verify_install",
                return_value=RoleReconciliationCoverage.FINGERPRINT,
            )
        )

    def test_all_registration_migration_crash_boundaries_converge_forward(self) -> None:
        scenarios = (
            "before-config",
            "after-config",
            "after-receipt",
            "before-tombstone",
            "after-tombstone",
        )
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home, repo, sha, state_fd, intent = self.environment(root)
                publish_calls = 0
                real_publish = DEPLOY.publish_journaled_file

                def crash_at_publication(*args: object, **kwargs: object) -> object:
                    nonlocal publish_calls
                    publish_calls += 1
                    target = 1 if scenario == "before-config" else 2
                    if scenario in {"before-config", "after-config"} and publish_calls == target:
                        raise self.SimulatedCrash()
                    return real_publish(*args, **kwargs)

                try:
                    with ExitStack() as stack:
                        self.gateway_context(stack, home, repo, root / "deploy-state")
                        if scenario in {"before-config", "after-config"}:
                            stack.enter_context(
                                mock.patch.object(
                                    DEPLOY,
                                    "publish_journaled_file",
                                    side_effect=crash_at_publication,
                                )
                            )
                        elif scenario == "after-receipt":
                            stack.enter_context(
                                mock.patch.object(
                                    DEPLOY,
                                    "mark_role_transaction_committed",
                                    side_effect=self.SimulatedCrash(),
                                )
                            )
                        elif scenario == "before-tombstone":
                            stack.enter_context(
                                mock.patch.object(
                                    DEPLOY,
                                    "publish_migration_tombstone",
                                    side_effect=self.SimulatedCrash(),
                                )
                            )
                        else:
                            stack.enter_context(
                                mock.patch.object(
                                    DEPLOY,
                                    "finalize_publication",
                                    side_effect=self.SimulatedCrash(),
                                )
                            )
                        with self.assertRaises(self.SimulatedCrash):
                            DEPLOY.reconcile_roles(
                                sha,
                                PinnedBundleCoverage.VERSION,
                                state_fd,
                                intent,
                            )

                    with ExitStack() as stack:
                        self.gateway_context(stack, home, repo, root / "deploy-state")
                        durable = DEPLOY.load_intent(state_fd)
                        self.assertIsNotNone(durable)
                        self.assertEqual(
                            durable["role_transaction"]["operation"],
                            "migrate-v1-registration",
                        )
                        DEPLOY.recover_promotion_intent(state_fd)
                        DEPLOY.recover_promotion_intent(state_fd)
                        self.assertIsNone(DEPLOY.load_intent(state_fd))
                        deployment = DEPLOY.load_state(state_fd)
                        self.assertIsNotNone(deployment)
                        self.assertEqual(
                            deployment["schema"], DEPLOY.DEPLOY_RECEIPT_SCHEMA
                        )
                        self.assertIsNotNone(DEPLOY.load_migration_tombstone(state_fd))
                        live_config = (home / "config.toml").read_bytes()
                        self.assertNotIn(DEPLOY.legacy_role_block(), live_config)
                        live_receipt = DEPLOY.parse_role_receipt(
                            (
                                (
                                    home
                                    / "state"
                                    / DEPLOY.ROLE_RECEIPT_FILE.name
                                ).read_bytes(),
                                (
                                    home
                                    / "state"
                                    / DEPLOY.ROLE_RECEIPT_FILE.name
                                ).stat(),
                            )
                        )
                        self.assertEqual(
                            live_receipt["schema"], DEPLOY.ROLE_RECEIPT_SCHEMA
                        )
                        self.assertEqual(
                            live_receipt["archives"],
                            DEPLOY.legacy_role_receipt_value()["archives"],
                        )
                finally:
                    os.close(state_fd)

    def test_tombstone_blocks_replay_and_conflicting_publication(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home, repo, sha, state_fd, intent = self.environment(root)
            try:
                with ExitStack() as stack:
                    self.gateway_context(stack, home, repo, root / "deploy-state")
                    DEPLOY.reconcile_roles(
                        sha,
                        PinnedBundleCoverage.VERSION,
                        state_fd,
                        intent,
                    )
                with ExitStack() as stack:
                    self.gateway_context(stack, home, repo, root / "deploy-state")
                    durable = DEPLOY.load_intent(state_fd)
                    self.assertIsNotNone(durable)
                    transaction = durable["role_transaction"]
                    conflicting = dict(transaction)
                    conflicting_tombstone = DEPLOY.build_migration_tombstone(
                        transaction["legacy_fingerprint"],
                        "f" * 40,
                        transaction["role_generation"],
                        transaction["role_receipt_sha256"],
                    )
                    conflicting["tombstone_b64"] = DEPLOY.encode_journal_bytes(
                        conflicting_tombstone
                    )
                    conflicting["tombstone_sha256"] = hashlib.sha256(
                        conflicting_tombstone
                    ).hexdigest()
                    with self.assertRaisesRegex(DEPLOY.DeployError, "conflicting"):
                        DEPLOY.publish_migration_tombstone(state_fd, conflicting)

                    (home / "config.toml").write_bytes(
                        b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n\n'
                        + DEPLOY.legacy_role_block()
                    )
                    receipt = home / "state" / DEPLOY.ROLE_RECEIPT_FILE.name
                    receipt.write_bytes(DEPLOY.legacy_role_receipt_bytes())
                    with self.assertRaisesRegex(DEPLOY.DeployError, "reappeared"):
                        DEPLOY.reconcile_roles(
                            sha,
                            PinnedBundleCoverage.VERSION,
                            state_fd,
                            durable,
                        )
            finally:
                os.close(state_fd)


class UnsafeDeploymentStateFileCoverage(unittest.TestCase):
    """Reject unsafe durable gateway files before consuming their contents."""

    MIGRATION_STAGE = (
        f".{DEPLOY.PLUGIN}-v1-registration."
        "11111111111111111111111111111111.tmp"
    )

    @staticmethod
    def migration_material() -> tuple[dict[str, object], bytes]:
        legacy_fingerprint = "a" * 64
        requested_sha = "b" * 40
        role_generation = "c" * 64
        role_receipt_sha256 = "d" * 64
        tombstone = DEPLOY.build_migration_tombstone(
            legacy_fingerprint,
            requested_sha,
            role_generation,
            role_receipt_sha256,
        )
        transaction = {
            "legacy_fingerprint": legacy_fingerprint,
            "role_generation": role_generation,
            "role_receipt_sha256": role_receipt_sha256,
            "tombstone_b64": DEPLOY.encode_journal_bytes(tombstone),
            "tombstone_exchange_name": (
                UnsafeDeploymentStateFileCoverage.MIGRATION_STAGE
            ),
            "tombstone_sha256": hashlib.sha256(tombstone).hexdigest(),
        }
        return transaction, tombstone

    @staticmethod
    def deployment_receipt_payload() -> bytes:
        value = RoleReconciliationCoverage().state()
        DEPLOY.validate_deploy_receipt(value)
        return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")

    @staticmethod
    def promotion_intent_payload() -> bytes:
        value = {
            "schema": DEPLOY.PROMOTION_INTENT_SCHEMA,
            "repository": DEPLOY.REPOSITORY,
            "marketplace": DEPLOY.MARKETPLACE,
            "plugin": DEPLOY.PLUGIN,
            "requested_sha": "a" * 40,
            "previous_receipt": None,
            "role_transaction": None,
        }
        DEPLOY.validate_intent(value)
        return (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")

    @staticmethod
    def make_unsafe(path: Path, scenario: str, payload: bytes) -> object | None:
        if scenario == "type":
            path.mkdir(mode=0o700)
            return None
        if scenario == "symlink":
            target = path.with_name(f"{path.name}.target")
            target.write_bytes(payload)
            target.chmod(0o600)
            path.symlink_to(target.name)
            return None
        path.write_bytes(payload)
        path.chmod(0o600)
        if scenario == "mode":
            path.chmod(0o640)
        elif scenario == "nlink":
            os.link(path, path.with_name(f"{path.name}.hardlink"))
        elif scenario == "owner":
            return mock.patch.object(
                DEPLOY.os,
                "geteuid",
                return_value=os.geteuid() + 1,
            )
        else:
            raise AssertionError(f"unsupported unsafe scenario: {scenario}")
        return None

    def assert_unsafe_matrix(
        self,
        filename: str,
        operation: Callable[[int], object],
        *,
        lock: bool = False,
        payload: bytes = b"",
    ) -> None:
        for scenario in ("owner", "mode", "type", "nlink", "symlink"):
            with (
                self.subTest(file=filename, scenario=scenario),
                tempfile.TemporaryDirectory() as temporary,
            ):
                state = Path(temporary) / "state"
                state.mkdir(mode=0o700)
                state_fd = os.open(state, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    owner_patch = self.make_unsafe(
                        state / filename,
                        scenario,
                        payload,
                    )
                    with ExitStack() as stack:
                        if owner_patch is not None:
                            stack.enter_context(owner_patch)
                        expected = (
                            OSError
                            if lock and scenario in {"type", "symlink"}
                            else DEPLOY.DeployError
                        )
                        with self.assertRaises(expected) as raised:
                            operation(state_fd)
                    if isinstance(raised.exception, DEPLOY.DeployError):
                        expected_code = None if lock else "receipt-corruption"
                        self.assertEqual(raised.exception.error_code, expected_code)
                finally:
                    os.close(state_fd)

    def test_deployment_lock_rejects_unsafe_file_matrix(self) -> None:
        self.assert_unsafe_matrix(
            DEPLOY.LOCK_FILE.name,
            DEPLOY.open_lock_file,
            lock=True,
        )

    def test_deployment_lock_create_or_open_failure_is_rejected(self) -> None:
        for failure in (PermissionError("create denied"), OSError("open failed")):
            with self.subTest(failure=type(failure).__name__), mock.patch.object(
                DEPLOY.os,
                "open",
                side_effect=failure,
            ) as opener:
                with self.assertRaises(type(failure)):
                    DEPLOY.open_lock_file(37)
                opener.assert_called_once_with(
                    DEPLOY.LOCK_FILE.name,
                    os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=37,
                )

    def test_deployment_receipt_rejects_unsafe_file_matrix(self) -> None:
        self.assert_unsafe_matrix(
            DEPLOY.STATE_FILE.name,
            DEPLOY.load_state,
            payload=self.deployment_receipt_payload(),
        )

    def test_promotion_intent_rejects_unsafe_file_matrix(self) -> None:
        self.assert_unsafe_matrix(
            DEPLOY.INTENT_FILE.name,
            DEPLOY.load_intent,
            payload=self.promotion_intent_payload(),
        )

    def test_registration_migration_tombstone_rejects_unsafe_file_matrix(
        self,
    ) -> None:
        _, tombstone = self.migration_material()
        self.assert_unsafe_matrix(
            DEPLOY.MIGRATION_TOMBSTONE_FILE.name,
            DEPLOY.load_migration_tombstone,
            payload=tombstone,
        )

    def test_fixed_migration_stage_rejects_unsafe_file_matrix(self) -> None:
        transaction, tombstone = self.migration_material()
        self.assert_unsafe_matrix(
            self.MIGRATION_STAGE,
            lambda state_fd: DEPLOY.publish_migration_tombstone(
                state_fd,
                transaction,
            ),
            payload=tombstone,
        )


if __name__ == "__main__":
    unittest.main()
