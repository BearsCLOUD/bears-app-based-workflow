#!/usr/bin/env python3
"""Exercise source-safe installer state import helpers in disposable directories."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


RUNNER_DIR = Path(__file__).resolve().parent
INSTALLER = RUNNER_DIR / "install-runner.sh"
PLUGIN = "bears-app-based-workflow"
REPOSITORY = "https://github.com/BearsCLOUD/bears-app-based-workflow.git"
RECEIPT_NAME = f"{PLUGIN}.json"
LOCK_NAME = f"{PLUGIN}.lock"
STAGE_NAME = f".{PLUGIN}.legacy-state-import.stage"
TOMBSTONE_NAME = f"{PLUGIN}.legacy-state-imported.json"
ROLE_NAMES = tuple(
    sorted(path.stem for path in RUNNER_DIR.parents[1].joinpath("agents").glob("*.toml"))
)


@dataclass(frozen=True)
class ImportFixture:
    root: Path
    state_root: Path
    state: Path
    legacy: Path
    source: bytes

    @property
    def legacy_receipt(self) -> Path:
        return self.legacy / RECEIPT_NAME

    @property
    def legacy_lock(self) -> Path:
        return self.legacy / LOCK_NAME

    @property
    def destination_receipt(self) -> Path:
        return self.state / RECEIPT_NAME

    @property
    def destination_lock(self) -> Path:
        return self.state / LOCK_NAME

    @property
    def stage(self) -> Path:
        return self.state / STAGE_NAME

    @property
    def tombstone(self) -> Path:
        return self.state / TOMBSTONE_NAME


def json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def v1_receipt(marker: str = "a") -> bytes:
    return json_bytes(
        {
            "schema": "bears-plugin-deploy-state.v1",
            "repository": REPOSITORY,
            "marketplace": PLUGIN,
            "plugin": PLUGIN,
            "sha": marker * 40,
            "version": "0.1.0+codex.20260711074119",
            "payload_fingerprint": marker * 64,
        }
    )


def v2_receipt(state: Path) -> bytes:
    generation = "c" * 64
    source_paths = (
        ".codex-plugin/plugin.json",
        "agents/README.md",
        *(f"agents/{name}.toml" for name in ROLE_NAMES),
    )
    blobs = {
        relative: {"git_oid": "d" * 40, "sha256": "e" * 64}
        for relative in source_paths
    }
    profiles = [
        {
            "name": name,
            "config_file": str(state / "role-generations" / generation / f"{name}.toml"),
            "git_oid": blobs[f"agents/{name}.toml"]["git_oid"],
            "sha256": blobs[f"agents/{name}.toml"]["sha256"],
        }
        for name in ROLE_NAMES
    ]
    return json_bytes(
        {
            "schema": "bears-plugin-deploy-state.v2",
            "repository": REPOSITORY,
            "marketplace": PLUGIN,
            "plugin": PLUGIN,
            "sha": "c" * 40,
            "version": "0.1.0+codex.20260711235959",
            "payload_fingerprint": "c" * 64,
            "role_generation": generation,
            "role_count": len(ROLE_NAMES),
            "role_catalog_sha256": generation,
            "role_receipt_sha256": "f" * 64,
            "role_source_blobs": blobs,
            "role_profiles": profiles,
        }
    )


def private_write(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    path.chmod(0o600)


@contextmanager
def import_fixture() -> ImportFixture:
    with tempfile.TemporaryDirectory(prefix="bears-plugin-state-test.") as temporary:
        root = Path(temporary)
        root.chmod(0o700)
        legacy = root / "legacy"
        legacy.mkdir(mode=0o700)
        source = v1_receipt()
        private_write(legacy / RECEIPT_NAME, source)
        private_write(legacy / LOCK_NAME, b"")
        yield ImportFixture(
            root=root,
            state_root=root / "state",
            state=root / "state/ai1",
            legacy=legacy,
            source=source,
        )


@contextmanager
def held_lock(path: Path):
    descriptor = os.open(path, os.O_RDWR | os.O_CLOEXEC)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(descriptor)


class InstallRunnerStateCoverage(unittest.TestCase):
    maxDiff = None

    def run_import(
        self, fixture: ImportFixture, crash_point: str = ""
    ) -> subprocess.CompletedProcess[str]:
        command = (
            'source "$1"; '
            '_install_runner_import_deployment_state '
            '"$2" "$3" "$4" "$5" "$6" test "$7" "$8"'
        )
        return subprocess.run(
            [
                "/usr/bin/bash",
                "-c",
                command,
                "install-runner-state-test",
                str(INSTALLER),
                str(os.geteuid()),
                str(os.getegid()),
                str(fixture.state_root),
                str(fixture.state),
                str(fixture.legacy),
                str(fixture.root),
                crash_point,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_failure(self, result: subprocess.CompletedProcess[str], message: str) -> None:
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(message, result.stderr)

    def assert_private_regular(self, path: Path) -> None:
        metadata = path.stat()
        self.assertTrue(stat.S_ISREG(metadata.st_mode))
        self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
        self.assertEqual(metadata.st_uid, os.geteuid())
        self.assertEqual(metadata.st_gid, os.getegid())
        self.assertEqual(metadata.st_nlink, 1)

    def test_sourcing_is_inert_and_ignores_path_environment(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bears-plugin-source-test.") as temporary:
            root = Path(temporary)
            command = r'''
before_umask="$(umask)"
before_trap="$(trap -p EXIT || :)"
before_flags="$-"
stage=caller-stage
archive_tmp=caller-archive
sudoers_tmp=caller-sudoers
unit_tmp=caller-unit
source "$1" || exit 1
[[ "$(umask)" == "$before_umask" ]] || exit 1
[[ "$(trap -p EXIT || :)" == "$before_trap" ]] || exit 1
[[ "$-" == "$before_flags" ]] || exit 1
[[ "$stage" == caller-stage ]] || exit 1
[[ "$archive_tmp" == caller-archive ]] || exit 1
[[ "$sudoers_tmp" == caller-sudoers ]] || exit 1
[[ "$unit_tmp" == caller-unit ]] || exit 1
[[ "$DEPLOY_STATE_ROOT" == /var/lib/bears-plugin-deploy ]] || exit 1
[[ "$DEPLOY_STATE_DIR" == /var/lib/bears-plugin-deploy/ai1 ]] || exit 1
[[ ! -e "$2/state" ]] || exit 1
'''
            environment = dict(os.environ)
            environment["DEPLOY_STATE_ROOT"] = str(root / "injected")
            environment["DEPLOY_STATE_DIR"] = str(root / "injected/leaf")
            result = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    command,
                    "source-test",
                    str(INSTALLER),
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            self.assert_success(result)

    def test_cgroup_populated_predicate_uses_real_events_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bears-plugin-cgroup-test.") as temporary:
            root = Path(temporary)
            service = root / "runner.slice"
            service.mkdir()
            events = service / "cgroup.events"
            command = (
                'source "$1"; '
                '_install_runner_service_cgroup_empty test.service /runner.slice "$2"'
            )
            events.write_text("populated 0\nfrozen 0\n")
            empty = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    command,
                    "cgroup-test",
                    str(INSTALLER),
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assert_success(empty)
            events.write_text("populated 1\nfrozen 0\n")
            nonempty = subprocess.run(
                [
                    "/usr/bin/bash",
                    "-c",
                    command,
                    "cgroup-test",
                    str(INSTALLER),
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(nonempty.returncode, 0)

    def test_first_import_and_identical_prepromotion_rerun(self) -> None:
        with import_fixture() as fixture:
            self.assert_success(self.run_import(fixture))
            self.assertEqual(fixture.destination_receipt.read_bytes(), fixture.source)
            self.assert_private_regular(fixture.destination_receipt)
            self.assert_private_regular(fixture.destination_lock)
            tombstone = json.loads(fixture.tombstone.read_bytes())
            self.assertEqual(tombstone["source_path"], str(fixture.legacy_receipt))
            self.assertEqual(
                tombstone["source_sha256"], hashlib.sha256(fixture.source).hexdigest()
            )
            self.assertFalse(fixture.stage.exists())

            before = fixture.tombstone.read_bytes()
            self.assert_success(self.run_import(fixture))
            self.assertEqual(fixture.destination_receipt.read_bytes(), fixture.source)
            self.assertEqual(fixture.tombstone.read_bytes(), before)

    def test_evolved_valid_v2_destination_rerun(self) -> None:
        with import_fixture() as fixture:
            self.assert_success(self.run_import(fixture))
            evolved = v2_receipt(fixture.state)
            private_write(fixture.destination_receipt, evolved)
            self.assert_success(self.run_import(fixture))
            self.assertEqual(fixture.destination_receipt.read_bytes(), evolved)

    def test_source_drift_and_bad_tombstone_fail_closed(self) -> None:
        with import_fixture() as fixture:
            self.assert_success(self.run_import(fixture))
            private_write(fixture.legacy_receipt, v1_receipt("b"))
            self.assert_failure(self.run_import(fixture), "drifted from its import tombstone")
        with import_fixture() as fixture:
            self.assert_success(self.run_import(fixture))
            private_write(fixture.tombstone, b"{}\n")
            self.assert_failure(self.run_import(fixture), "tombstone shape is invalid")

    def test_missing_tombstone_and_destination_conflict_fail_closed(self) -> None:
        with import_fixture() as fixture:
            self.assert_success(self.run_import(fixture))
            private_write(fixture.destination_receipt, v2_receipt(fixture.state))
            fixture.tombstone.unlink()
            self.assert_failure(self.run_import(fixture), "conflicts with the legacy receipt")
        with import_fixture() as fixture:
            fixture.state_root.mkdir(mode=0o700)
            fixture.state.mkdir(mode=0o700)
            private_write(fixture.destination_receipt, v1_receipt("b"))
            self.assert_failure(self.run_import(fixture), "conflicts with the legacy receipt")

    def test_destination_and_legacy_locks_are_nonblocking(self) -> None:
        with import_fixture() as fixture:
            with held_lock(fixture.legacy_lock):
                self.assert_failure(
                    self.run_import(fixture), "legacy deployment state lock is busy"
                )
        with import_fixture() as fixture:
            self.assert_success(self.run_import(fixture))
            with held_lock(fixture.destination_lock):
                self.assert_failure(
                    self.run_import(fixture), "gateway deployment state lock is busy"
                )

    def test_stage_crash_before_receipt_publish_recovers_on_rerun(self) -> None:
        with import_fixture() as fixture:
            crashed = self.run_import(fixture, "after-stage-write-before-receipt")
            self.assert_failure(crashed, "after import stage write before receipt publication")
            self.assertEqual(fixture.stage.read_bytes(), fixture.source)
            self.assertFalse(fixture.destination_receipt.exists())
            self.assertFalse(fixture.tombstone.exists())
            self.assert_success(self.run_import(fixture))
            self.assertEqual(fixture.destination_receipt.read_bytes(), fixture.source)
            self.assertTrue(fixture.tombstone.exists())
            self.assertFalse(fixture.stage.exists())

    def test_receipt_before_tombstone_crash_recovers_on_rerun(self) -> None:
        with import_fixture() as fixture:
            crashed = self.run_import(fixture, "after-receipt-before-tombstone")
            self.assert_failure(crashed, "after receipt publication before tombstone")
            self.assertEqual(fixture.destination_receipt.read_bytes(), fixture.source)
            self.assertFalse(fixture.stage.exists())
            self.assertFalse(fixture.tombstone.exists())
            self.assert_success(self.run_import(fixture))
            self.assertTrue(fixture.tombstone.exists())


if __name__ == "__main__":
    unittest.main()
