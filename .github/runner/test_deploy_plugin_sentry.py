#!/usr/bin/env python3
"""Machine-only unit stubs for the fixed deploy gateway."""

from __future__ import annotations

from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import sys
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


class RoleReconciliationCoverage(unittest.TestCase):
    SHA = "a" * 40
    VERSION = "0.1.0+codex.20260711000000"
    FINGERPRINT = "f" * 64

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

    def test_malformed_or_unowned_config_fails_closed(self) -> None:
        catalog = self.catalog()
        with self.assertRaises(DEPLOY.DeployError):
            DEPLOY.parse_config(b"[broken", "stub config")
        with self.assertRaises(DEPLOY.DeployError):
            DEPLOY.desired_role_config(
                b'[agents.unowned]\nconfig_file = "/tmp/unowned.toml"\n',
                self.VERSION,
                catalog,
            )

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


if __name__ == "__main__":
    unittest.main()
