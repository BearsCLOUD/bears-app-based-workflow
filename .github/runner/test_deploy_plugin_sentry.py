#!/usr/bin/env python3
"""Deterministic authored coverage for the fixed deploy gateway."""

from __future__ import annotations

from contextlib import ExitStack
import importlib.util
import hashlib
import json
import os
from pathlib import Path
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

    def test_authentic_predecessor_receipt_migrates_to_v2_eleven(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            profiles = root / "legacy"
            profiles.mkdir()
            catalog: dict[str, str] = {}
            records: list[dict[str, str]] = []
            for name in DEPLOY.LEGACY_ROLE_NAMES:
                data = subprocess.run(
                    ["git", "show", f"22a6017:agents/{name}.toml"],
                    cwd=MODULE_PATH.parents[2],
                    check=True,
                    stdout=subprocess.PIPE,
                ).stdout
                path = profiles / f"{name}.toml"
                path.write_bytes(data)
                catalog[name] = str(path)
                digest = hashlib.sha256(data).hexdigest()
                self.assertEqual(digest, DEPLOY.LEGACY_ROLE_SHA256[name])
                records.append({"name": name, "config_file": str(path), "sha256": digest})
            block = DEPLOY.role_block(DEPLOY.LEGACY_ROLE_VERSION, catalog)
            config = b'[agents.personal]\nconfig_file = "/opt/personal.toml"\n\n' + block
            receipt_value = {
                "schema": DEPLOY.LEGACY_ROLE_RECEIPT_SCHEMA,
                "plugin": DEPLOY.PLUGIN,
                "version": DEPLOY.LEGACY_ROLE_VERSION,
                "status": "installed",
                "changed": True,
                "role_count": 9,
                "managed_digest": hashlib.sha256(block).hexdigest(),
                "managed_joiner_added": False,
                "managed_profiles": records,
                "archives": [],
            }
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt_value), encoding="utf-8")
            receipt_path.chmod(0o600)
            receipt = (receipt_path.read_bytes(), receipt_path.stat())
            previous = DEPLOY.validate_owned_role_state(config, receipt)
            self.assertEqual(previous["role_count"], 9)
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
            self.assertEqual([row["name"] for row in migrated["managed_profiles"]], list(self.EXPECTED_NAMES))

            receipt_value["version"] = "0.1.0+codex.20260711144359"
            receipt_path.write_text(json.dumps(receipt_value), encoding="utf-8")
            with self.assertRaises(DEPLOY.DeployError):
                DEPLOY.validate_owned_role_state(config, (receipt_path.read_bytes(), receipt_path.stat()))

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
            intent = DEPLOY.save_intent(state_fd, sha, legacy_state)

            def crash_before_finalize(_: object) -> None:
                raise self.SimulatedCrash()

            try:
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


if __name__ == "__main__":
    unittest.main()
