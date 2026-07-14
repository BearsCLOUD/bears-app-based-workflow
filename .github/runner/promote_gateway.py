#!/usr/bin/env python3
"""Root-owned exact-SHA gateway updater and non-root promotion bridge.

This executable is installed by ``install-runner.sh``.  It treats the
requested repository revision as data: it fetches only the fixed ``main``
history, materializes the hash-locked gateway in a root-owned staging tree,
and executes that gateway as ``ai1``. A failed promotion restores the prior
gateway unless a graphless v5 receipt already binds the active gateway revision.
"""

from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Mapping


REPOSITORY = "https://github.com/BearsCLOUD/bears-app-based-workflow.git"
MAIN_REF = "refs/remotes/origin/main"
SHA_RE = re.compile(r"[0-9a-f]{40}")
TOKEN_RE = re.compile(rb"[\x21-\x7e]+")
TOKEN_MAX_BYTES = 1024
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")
VERSION_RE = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:\+codex\.\d{14})?")
SOURCE_PREFIX = ".github/runner/bears_deploy/"
LAUNCHER_SOURCE = ".github/runner/deploy_plugin.py"
LOCK_SOURCE = ".github/runner/sentry-requirements.lock"
PACKAGE_ROOT = Path("/usr/local/lib/bears-plugin-deploy")
LAUNCHER = Path("/usr/local/sbin/deploy-bears-app-based-workflow")
STATE_ROOT = Path("/var/lib/bears-plugin-gateway-update")
LOCK_FILE = STATE_ROOT / "update.lock"
JOURNAL_FILE = STATE_ROOT / "transaction.json"
DEPLOY_STATE_DIR = Path("/var/lib/bears-plugin-deploy/ai1")
DEPLOY_RECEIPT = DEPLOY_STATE_DIR / "bears-app-based-workflow.json"
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v5"
PACKAGE_BACKUP = Path("/usr/local/lib/bears-plugin-deploy.previous")
LAUNCHER_BACKUP = Path("/usr/local/sbin/deploy-bears-app-based-workflow.previous")
GIT = "/usr/bin/git"
PYTHON = "/usr/bin/python3"
RUNUSER = "/usr/sbin/runuser"
TIMEOUT = "/usr/bin/timeout"
ENV = {
    "HOME": "/root",
    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "LANG": "C.UTF-8",
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
    "PIP_CONFIG_FILE": "/dev/null",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "PIP_NO_INPUT": "1",
}
MAX_BLOB_BYTES = 512 * 1024
MAX_SOURCE_BYTES = 4 * 1024 * 1024
MAX_GATEWAY_OUTPUT = 128 * 1024
MAX_DEPLOY_RECEIPT_BYTES = 64 * 1024
GATEWAY_TIMEOUT_SECONDS = 600
GATEWAY_KILL_AFTER_SECONDS = 10
GATEWAY_COMMUNICATE_GRACE_SECONDS = 20
ALLOWED_REQUIREMENTS = frozenset({"sentry-sdk", "urllib3", "certifi"})
V5_RECEIPT_FIELDS = frozenset(
    {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "sha",
        "version",
        "payload_fingerprint",
        "role_generation",
        "role_count",
        "role_catalog_sha256",
        "role_receipt_sha256",
        "role_source_blobs",
        "role_profiles",
    }
)
REQUIRED_MODULES = frozenset(
    {
        "__init__.py",
        "cli.py",
        "constants.py",
        "marketplace.py",
        "process.py",
        "promotion.py",
        "role_renderer.py",
        "telemetry.py",
    }
)


class GatewayUpdateError(RuntimeError):
    """A fail-closed updater or rollback error."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _valid_v5_roles(receipt: dict[str, Any]) -> bool:
    generation = receipt.get("role_generation")
    blobs = receipt.get("role_source_blobs")
    profiles = receipt.get("role_profiles")
    if not isinstance(profiles, list):
        return False
    profile_names = tuple(
        record.get("name")
        for record in profiles
        if isinstance(record, dict) and isinstance(record.get("name"), str)
    )
    if (
        len(profile_names) != len(profiles)
        or profile_names != tuple(sorted(set(profile_names)))
        or any(
            re.fullmatch(r"[a-z][a-z0-9-]{0,63}", name) is None
            for name in profile_names
        )
    ):
        return False
    expected_sources = {
        ".codex-plugin/plugin.json",
        "agents/README.md",
        *(f"agents/{name}.toml" for name in profile_names),
    }
    legacy_jsonless = bool(
        isinstance(receipt.get("version"), str)
        and re.fullmatch(r"\d+\.\d+\.\d+\+codex\.\d{14}", receipt["version"])
    )
    has_definition_sources = isinstance(blobs, dict) and any(
        path.startswith("role-definitions/") for path in blobs
    )
    if has_definition_sources or not legacy_jsonless:
        expected_sources.update(
            {
                "role-definitions/capability-catalog.v1.json",
                *(f"role-definitions/{name}.json" for name in profile_names),
            }
        )
    if (
        not isinstance(generation, str)
        or FINGERPRINT_RE.fullmatch(generation) is None
        or receipt.get("role_catalog_sha256") != generation
        or not isinstance(receipt.get("role_count"), int)
        or isinstance(receipt.get("role_count"), bool)
        or not 1 <= receipt["role_count"] <= 64
        or len(profiles) != receipt["role_count"]
        or not isinstance(blobs, dict)
        or set(blobs) != expected_sources
    ):
        return False
    for record in blobs.values():
        if (
            not isinstance(record, dict)
            or set(record) != {"git_oid", "sha256"}
            or not isinstance(record.get("git_oid"), str)
            or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", record["git_oid"]) is None
            or not isinstance(record.get("sha256"), str)
            or FINGERPRINT_RE.fullmatch(record["sha256"]) is None
        ):
            return False
    for name, record in zip(profile_names, profiles, strict=True):
        source = blobs[f"agents/{name}.toml"]
        expected_path = str(DEPLOY_STATE_DIR / "role-generations" / generation / f"{name}.toml")
        if (
            set(record) != {"name", "config_file", "git_oid", "sha256"}
            or record.get("name") != name
            or record.get("config_file") != expected_path
            or record.get("git_oid") != source["git_oid"]
            or record.get("sha256") != source["sha256"]
        ):
            return False
    return True


def _durable_v5_binds(requested: str) -> bool:
    """Read one private receipt without executing newly fetched gateway code."""
    directory = -1
    descriptor = -1
    try:
        account = pwd.getpwnam("ai1")
        directory = os.open(
            DEPLOY_STATE_DIR,
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        )
        directory_stat = os.fstat(directory)
        if (
            directory_stat.st_uid != account.pw_uid
            or directory_stat.st_gid != account.pw_gid
            or stat.S_IMODE(directory_stat.st_mode) != 0o700
        ):
            return False
        descriptor = os.open(
            DEPLOY_RECEIPT.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory,
        )
        receipt_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(receipt_stat.st_mode)
            or receipt_stat.st_nlink != 1
            or receipt_stat.st_uid != account.pw_uid
            or receipt_stat.st_gid != account.pw_gid
            or stat.S_IMODE(receipt_stat.st_mode) != 0o600
            or receipt_stat.st_size > MAX_DEPLOY_RECEIPT_BYTES
        ):
            return False
        payload = bytearray()
        while len(payload) <= MAX_DEPLOY_RECEIPT_BYTES:
            chunk = os.read(descriptor, min(4096, MAX_DEPLOY_RECEIPT_BYTES + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > MAX_DEPLOY_RECEIPT_BYTES:
            return False
        receipt = json.loads(payload.decode("utf-8"), object_pairs_hook=_strict_object)
    except (KeyError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if directory >= 0:
            os.close(directory)
    digest_fields = (
        "payload_fingerprint",
        "role_generation",
        "role_catalog_sha256",
        "role_receipt_sha256",
    )
    return bool(
        isinstance(receipt, dict)
        and set(receipt) == V5_RECEIPT_FIELDS
        and receipt.get("schema") == DEPLOY_RECEIPT_SCHEMA
        and receipt.get("repository") == REPOSITORY
        and receipt.get("marketplace") == "bears-app-based-workflow"
        and receipt.get("plugin") == "bears-app-based-workflow"
        and receipt.get("sha") == requested
        and isinstance(receipt.get("version"), str)
        and VERSION_RE.fullmatch(receipt["version"])
        and all(
            isinstance(receipt.get(field), str) and FINGERPRINT_RE.fullmatch(receipt[field])
            for field in digest_fields
        )
        and isinstance(receipt.get("role_count"), int)
        and not isinstance(receipt.get("role_count"), bool)
        and _valid_v5_roles(receipt)
    )


def _active_gateway_binds(requested: str) -> bool:
    """Require the active package and launcher to bind the requested source."""
    source_receipt = PACKAGE_ROOT / ".gateway-source.json"
    requirements = PACKAGE_ROOT / ".sentry-requirements.lock"
    package = PACKAGE_ROOT / "bears_deploy"
    try:
        _validate_stage(PACKAGE_ROOT)
        _validate_installed_file(source_receipt, 0o644)
        _validate_installed_file(LAUNCHER, 0o755)
        payload = source_receipt.read_bytes()
        if len(payload) > MAX_BLOB_BYTES:
            return False
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=_strict_object)
    except (
        GatewayUpdateError,
        OSError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return False
    digest_fields = {"launcher_sha256", "requirements_sha256"}
    if not (
        isinstance(value, dict)
        and set(value) == {
            "schema",
            "source_sha",
            "launcher_sha256",
            "requirements_sha256",
            "modules",
        }
        and value.get("schema") == "bears-plugin-gateway-source.v1"
        and value.get("source_sha") == requested
        and all(
            isinstance(value.get(field), str) and FINGERPRINT_RE.fullmatch(value[field])
            for field in digest_fields
        )
        and isinstance(value.get("modules"), dict)
        and REQUIRED_MODULES.issubset(value["modules"])
        and all(
            isinstance(name, str)
            and re.fullmatch(r"(?:__init__|[a-z][a-z0-9_]{0,63})\.py", name)
            and isinstance(digest, str)
            and FINGERPRINT_RE.fullmatch(digest)
            for name, digest in value["modules"].items()
        )
    ):
        return False

    modules: dict[str, str] = value["modules"]
    try:
        if not package.is_dir() or package.is_symlink():
            return False
        if {entry.name for entry in package.iterdir()} != set(modules):
            return False
        expected_files = {
            LAUNCHER: (0o755, value["launcher_sha256"]),
            requirements: (0o644, value["requirements_sha256"]),
            **{
                package / name: (0o644, digest)
                for name, digest in modules.items()
            },
        }
        total = 0
        for path, (mode, digest) in expected_files.items():
            _validate_installed_file(path, mode)
            data = path.read_bytes()
            if len(data) > MAX_BLOB_BYTES:
                return False
            total += len(data)
            if total > MAX_SOURCE_BYTES or hashlib.sha256(data).hexdigest() != digest:
                return False
    except (GatewayUpdateError, OSError):
        return False
    return True


def _diagnostic(value: str) -> str:
    normalized = " ".join(
        "".join(char if char.isascii() and char.isprintable() else " " for char in value).split()
    )
    return normalized[:509] + "..." if len(normalized) > 512 else normalized


def _run(
    argv: list[str],
    *,
    env: Mapping[str, str] | None = None,
    input_bytes: bytes | None = None,
    ok: tuple[int, ...] = (0,),
    timeout: int | None = 300,
) -> subprocess.CompletedProcess[bytes]:
    if not argv or argv[0] not in {GIT, PYTHON, RUNUSER}:
        raise GatewayUpdateError("attempted to invoke a non-fixed executable")
    try:
        result = subprocess.run(
            argv,
            env=dict(ENV if env is None else env),
            input=input_bytes,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GatewayUpdateError(f"fixed command invocation failed: {_diagnostic(str(exc))}") from exc
    if result.returncode not in ok:
        detail = _diagnostic((result.stderr or result.stdout).decode("utf-8", "replace"))
        raise GatewayUpdateError(
            f"fixed command failed with exit {result.returncode}: {detail or 'no diagnostic output'}"
        )
    return result


def _git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[bytes]:
    return _run(
        [
            GIT,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.file.allow=never",
            "-C",
            str(repo),
            *args,
        ],
        ok=ok,
    )


def _git_text(repo: Path, *args: str) -> str:
    return _git(repo, *args).stdout.decode("utf-8", "strict").strip()


def _read_token() -> bytes:
    raw = sys.stdin.buffer.read(TOKEN_MAX_BYTES + 1)
    if (
        len(raw) > TOKEN_MAX_BYTES
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
        or not 20 <= len(raw) - 1 <= TOKEN_MAX_BYTES
        or TOKEN_RE.fullmatch(raw[:-1]) is None
    ):
        raise GatewayUpdateError("missing or invalid GitHub job credential")
    return raw


def _authenticated_env(token: bytes) -> dict[str, str]:
    authorization = base64.b64encode(b"x-access-token:" + token[:-1]).decode("ascii")
    return {
        **ENV,
        "GIT_CONFIG_COUNT": "2",
        "GIT_CONFIG_KEY_0": "credential.helper",
        "GIT_CONFIG_VALUE_0": "",
        "GIT_CONFIG_KEY_1": "http.https://github.com/.extraHeader",
        "GIT_CONFIG_VALUE_1": f"Authorization: Basic {authorization}",
    }


def _fetch_requested(repository: Path, requested: str, token: bytes) -> None:
    _run([GIT, "init", "--bare", str(repository)])
    _git(repository, "remote", "add", "origin", REPOSITORY)
    fetch = [
        GIT,
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "protocol.file.allow=never",
        "-C",
        str(repository),
        "fetch",
        "--force",
        "--no-tags",
        "origin",
        "+refs/heads/main:" + MAIN_REF,
    ]
    _run(fetch, env=_authenticated_env(token))
    if _git_text(repository, "remote", "get-url", "--all", "origin") != REPOSITORY:
        raise GatewayUpdateError("repository origin drifted")
    if _git_text(repository, "rev-parse", "--verify", f"{requested}^{{commit}}") != requested:
        raise GatewayUpdateError("requested object is not an exact commit")
    if _git(repository, "merge-base", "--is-ancestor", requested, MAIN_REF, ok=(0, 1)).returncode:
        raise GatewayUpdateError("requested SHA is not reachable from fixed repository main")


def _source_blobs(repository: Path, requested: str) -> dict[str, bytes]:
    listing = _git(
        repository,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        requested,
        "--",
        SOURCE_PREFIX,
        LAUNCHER_SOURCE,
        LOCK_SOURCE,
    ).stdout
    blobs: dict[str, bytes] = {}
    total = 0
    for raw_record in listing.split(b"\0"):
        if not raw_record:
            continue
        try:
            metadata, raw_path = raw_record.split(b"\t", 1)
            mode, object_type, object_id = metadata.decode("ascii").split(" ")
            path = raw_path.decode("utf-8", "strict")
        except (UnicodeError, ValueError) as exc:
            raise GatewayUpdateError("malformed gateway source tree entry") from exc
        if mode not in {"100644", "100755"} or object_type != "blob":
            raise GatewayUpdateError(f"gateway source is not a regular blob: {path}")
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts:
            raise GatewayUpdateError("unsafe gateway source path")
        allowed = path in {LAUNCHER_SOURCE, LOCK_SOURCE} or (
            path.startswith(SOURCE_PREFIX)
            and "/" not in path[len(SOURCE_PREFIX) :]
            and path.endswith(".py")
        )
        if not allowed or path in blobs:
            raise GatewayUpdateError(f"unexpected gateway source path: {path}")
        data = _git(repository, "cat-file", "blob", object_id).stdout
        if len(data) > MAX_BLOB_BYTES:
            raise GatewayUpdateError(f"gateway source blob is too large: {path}")
        total += len(data)
        if total > MAX_SOURCE_BYTES:
            raise GatewayUpdateError("gateway source bundle is too large")
        blobs[path] = data
    expected = {LAUNCHER_SOURCE, LOCK_SOURCE}
    missing = expected - blobs.keys()
    module_names = {path.removeprefix(SOURCE_PREFIX) for path in blobs if path.startswith(SOURCE_PREFIX)}
    if missing or not REQUIRED_MODULES.issubset(module_names):
        raise GatewayUpdateError("gateway source bundle is incomplete")
    return blobs


def _validate_requirement_lock(data: bytes) -> None:
    try:
        logical = data.decode("ascii").replace("\\\n", " ").splitlines()
    except UnicodeError as exc:
        raise GatewayUpdateError("gateway requirement lock is not ASCII") from exc
    found: set[str] = set()
    pattern = re.compile(
        r"([a-z0-9-]+)==([0-9][A-Za-z0-9.]*)(?:\s+--hash=sha256:[0-9a-f]{64})+"
    )
    for line in logical:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = pattern.fullmatch(" ".join(stripped.split()))
        if match is None or match.group(1) not in ALLOWED_REQUIREMENTS or match.group(1) in found:
            raise GatewayUpdateError("gateway requirement lock is outside the fixed package set")
        found.add(match.group(1))
    if found != ALLOWED_REQUIREMENTS:
        raise GatewayUpdateError("gateway requirement lock is incomplete")


def _write_regular(path: Path, data: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        os.close(descriptor)


def _validate_stage(root: Path) -> None:
    allowed_roots = {"sentry_sdk", "urllib3", "certifi", "bears_deploy"}
    for child in root.iterdir():
        name = child.name
        if name.startswith(("sentry_sdk-", "urllib3-", "certifi-")) and name.endswith(".dist-info"):
            continue
        if name not in allowed_roots and name not in {".sentry-requirements.lock", ".gateway-source.json"}:
            raise GatewayUpdateError(f"unexpected installed gateway entry: {name}")
    for path in [root, *root.rglob("*")]:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or metadata.st_uid != 0 or metadata.st_gid != 0:
            raise GatewayUpdateError(f"unsafe gateway stage ownership or link: {path.name}")
        if stat.S_IMODE(metadata.st_mode) & 0o022:
            raise GatewayUpdateError(f"writable gateway stage entry: {path.name}")
        if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
            raise GatewayUpdateError(f"special gateway stage entry: {path.name}")
        if stat.S_ISDIR(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) & 0o005 != 0o005:
            raise GatewayUpdateError(f"gateway stage directory is not readable by its runtime: {path.name}")
        if stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) & 0o004 != 0o004:
            raise GatewayUpdateError(f"gateway stage file is not readable by its runtime: {path.name}")
        if stat.S_ISREG(metadata.st_mode) and (
            path.suffix in {".pth", ".so", ".dll", ".dylib"} or metadata.st_size > 4 * 1024 * 1024
        ):
            raise GatewayUpdateError(f"unsupported gateway stage file: {path.name}")


def _materialize_stage(parent: Path, blobs: dict[str, bytes], requested: str) -> Path:
    lock_data = blobs[LOCK_SOURCE]
    _validate_requirement_lock(lock_data)
    stage = Path(tempfile.mkdtemp(prefix=".bears-plugin-deploy.stage-", dir=parent))
    os.chmod(stage, 0o755)
    lock_path = stage / ".sentry-requirements.lock"
    _write_regular(lock_path, lock_data, 0o644)
    try:
        _run(
            [
                PYTHON,
                "-I",
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-deps",
                "--no-compile",
                "--require-hashes",
                "--only-binary=:all:",
                "--target",
                str(stage),
                "--requirement",
                str(lock_path),
            ]
        )
        package = stage / "bears_deploy"
        package.mkdir(mode=0o755)
        module_hashes: dict[str, str] = {}
        for path, data in sorted(blobs.items()):
            if not path.startswith(SOURCE_PREFIX):
                continue
            name = path.removeprefix(SOURCE_PREFIX)
            _write_regular(package / name, data, 0o644)
            module_hashes[name] = hashlib.sha256(data).hexdigest()
        receipt = {
            "schema": "bears-plugin-gateway-source.v1",
            "source_sha": requested,
            "launcher_sha256": hashlib.sha256(blobs[LAUNCHER_SOURCE]).hexdigest(),
            "requirements_sha256": hashlib.sha256(lock_data).hexdigest(),
            "modules": module_hashes,
        }
        _write_regular(
            stage / ".gateway-source.json",
            (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode(),
            0o644,
        )
        _validate_stage(stage)
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def _validate_installed_file(path: Path, mode: int) -> None:
    metadata = path.lstat()
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != mode
    ):
        raise GatewayUpdateError(f"unsafe installed gateway file: {path}")


def _sync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_journal(requested: str, state: str) -> None:
    if state not in {"activated", "committed"}:
        raise GatewayUpdateError("invalid gateway transaction state")
    data = (
        json.dumps(
            {"schema": "bears-plugin-gateway-update.v1", "sha": requested, "state": state},
            sort_keys=True,
        )
        + "\n"
    ).encode()
    temporary = JOURNAL_FILE.with_name(JOURNAL_FILE.name + ".tmp")
    temporary.unlink(missing_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, JOURNAL_FILE)
    _sync_directory(STATE_ROOT)


def _remove_path(path: Path) -> None:
    if path.is_symlink():
        raise GatewayUpdateError(f"refusing linked gateway transaction path: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _rollback() -> None:
    if PACKAGE_BACKUP.exists():
        _remove_path(PACKAGE_ROOT)
        os.replace(PACKAGE_BACKUP, PACKAGE_ROOT)
    if LAUNCHER_BACKUP.exists():
        _remove_path(LAUNCHER)
        os.replace(LAUNCHER_BACKUP, LAUNCHER)
    JOURNAL_FILE.unlink(missing_ok=True)
    _sync_directory(PACKAGE_ROOT.parent)
    _sync_directory(LAUNCHER.parent)
    _sync_directory(STATE_ROOT)


def _commit_active_gateway(requested: str) -> None:
    _write_journal(requested, "committed")
    _remove_path(PACKAGE_BACKUP)
    _remove_path(LAUNCHER_BACKUP)
    JOURNAL_FILE.unlink(missing_ok=True)
    _sync_directory(PACKAGE_ROOT.parent)
    _sync_directory(LAUNCHER.parent)
    _sync_directory(STATE_ROOT)


def _settle_active_gateway_after_failure(requested: str) -> bool:
    """Retain the only v5-capable gateway, otherwise restore its predecessor."""
    if _active_gateway_binds(requested) and _durable_v5_binds(requested):
        _commit_active_gateway(requested)
        return True
    _rollback()
    return False


def _recover_interrupted_transaction() -> None:
    if not JOURNAL_FILE.exists():
        if PACKAGE_BACKUP.exists() or LAUNCHER_BACKUP.exists():
            raise GatewayUpdateError("orphaned gateway backup requires operator repair")
        return
    _validate_installed_file(JOURNAL_FILE, 0o600)
    try:
        value = json.loads(JOURNAL_FILE.read_bytes())
    except (OSError, json.JSONDecodeError) as exc:
        raise GatewayUpdateError("gateway transaction journal is invalid") from exc
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "sha", "state"}
        or value.get("schema") != "bears-plugin-gateway-update.v1"
        or not isinstance(value.get("sha"), str)
        or SHA_RE.fullmatch(value["sha"]) is None
        or value.get("state") not in {"activated", "committed"}
    ):
        raise GatewayUpdateError("gateway transaction journal is invalid")
    if value["state"] == "activated":
        _settle_active_gateway_after_failure(value["sha"])
        return
    _remove_path(PACKAGE_BACKUP)
    _remove_path(LAUNCHER_BACKUP)
    JOURNAL_FILE.unlink()
    _sync_directory(PACKAGE_ROOT.parent)
    _sync_directory(LAUNCHER.parent)
    _sync_directory(STATE_ROOT)


def _activate(stage: Path, launcher_data: bytes, requested: str) -> None:
    _validate_stage(stage)
    _validate_stage(PACKAGE_ROOT)
    _validate_installed_file(LAUNCHER, 0o755)
    if not PACKAGE_ROOT.is_dir() or PACKAGE_ROOT.is_symlink():
        raise GatewayUpdateError("installed gateway package is unsafe")
    if PACKAGE_BACKUP.exists() or LAUNCHER_BACKUP.exists():
        raise GatewayUpdateError("gateway backup path is occupied")
    launcher_stage = LAUNCHER.with_name(LAUNCHER.name + f".stage-{os.getpid()}")
    _write_regular(launcher_stage, launcher_data, 0o755)
    _write_journal(requested, "activated")
    try:
        os.replace(PACKAGE_ROOT, PACKAGE_BACKUP)
        os.replace(stage, PACKAGE_ROOT)
        os.replace(LAUNCHER, LAUNCHER_BACKUP)
        os.replace(launcher_stage, LAUNCHER)
        _sync_directory(PACKAGE_ROOT.parent)
        _sync_directory(LAUNCHER.parent)
    except Exception:
        launcher_stage.unlink(missing_ok=True)
        _rollback()
        raise


def _terminate_gateway_group(process: subprocess.Popen[bytes]) -> None:
    """Terminate and reap the complete leased gateway process group."""
    for signal_number, wait_seconds in (
        (signal.SIGTERM, GATEWAY_KILL_AFTER_SECONDS),
        (signal.SIGKILL, GATEWAY_KILL_AFTER_SECONDS),
    ):
        try:
            os.killpg(process.pid, signal_number)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=wait_seconds)
            return
        except subprocess.TimeoutExpired:
            continue
    raise GatewayUpdateError("gateway process group could not be reaped")


def _capture_gateway_output(
    process: subprocess.Popen[bytes],
    token: bytes,
    timeout_seconds: int,
) -> tuple[bytes, bytes]:
    """Drain child pipes while retaining at most the diagnostic budget per stream."""
    if process.stdin is None or process.stdout is None or process.stderr is None:
        raise GatewayUpdateError("gateway process pipes are unavailable")
    try:
        try:
            process.stdin.write(token)
            process.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()

        output = bytearray()
        errors = bytearray()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, output)
        selector.register(process.stderr, selectors.EVENT_READ, errors)
        deadline = time.monotonic() + timeout_seconds
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(process.args, timeout_seconds)
                for key, _ in selector.select(min(remaining, 0.25)):
                    chunk = os.read(key.fd, 8192)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    target: bytearray = key.data
                    available = MAX_GATEWAY_OUTPUT - len(target)
                    if available > 0:
                        target.extend(chunk[:available])
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(process.args, timeout_seconds)
            process.wait(timeout=remaining)
        finally:
            selector.close()
        return bytes(output), bytes(errors)
    finally:
        process.stdout.close()
        process.stderr.close()


def _gateway_child_env() -> list[str]:
    child_env = [
        "HOME=/home/ai1",
        "CODEX_HOME=/srv/bears/codex/ai1",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "LANG=C.UTF-8",
    ]
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        value = os.environ.get(name, "")
        if value.isdigit():
            child_env.append(f"{name}={value}")
    return child_env


def _exec_gateway_child(lease_value: str, requested: str) -> None:
    """Close the root lease in trusted code before execing the non-root gateway."""
    if SHA_RE.fullmatch(requested) is None or not lease_value.isdigit():
        raise GatewayUpdateError("invalid supervised gateway arguments")
    lease_descriptor = int(lease_value)
    if lease_descriptor <= 2:
        raise GatewayUpdateError("invalid supervised gateway lease")
    try:
        lease = os.fstat(lease_descriptor)
        lock = LOCK_FILE.stat()
    except OSError as exc:
        raise GatewayUpdateError("supervised gateway lease is unavailable") from exc
    if (
        not stat.S_ISREG(lease.st_mode)
        or (lease.st_dev, lease.st_ino) != (lock.st_dev, lock.st_ino)
        or lease.st_uid != 0
        or lease.st_gid != 0
        or stat.S_IMODE(lease.st_mode) != 0o600
    ):
        raise GatewayUpdateError("supervised gateway lease is invalid")
    try:
        fcntl.flock(lease_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise GatewayUpdateError("supervised gateway lease is not held") from exc
    os.close(lease_descriptor)
    argv = [
        RUNUSER,
        "-u",
        "ai1",
        "--",
        "/usr/bin/env",
        "-i",
        *_gateway_child_env(),
        str(LAUNCHER),
        requested,
    ]
    os.execve(RUNUSER, argv, ENV)
    raise GatewayUpdateError("supervised gateway exec returned unexpectedly")


def _run_gateway(
    requested: str,
    token: bytes,
    lease_descriptor: int,
) -> subprocess.CompletedProcess[bytes]:
    """Run one bounded non-root gateway while its supervisor leases the root lock."""
    supervisor_env = dict(ENV)
    for name in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        value = os.environ.get(name, "")
        if value.isdigit():
            supervisor_env[name] = value
    argv = [
        TIMEOUT,
        "--signal=TERM",
        f"--kill-after={GATEWAY_KILL_AFTER_SECONDS}s",
        f"{GATEWAY_TIMEOUT_SECONDS}s",
        PYTHON,
        str(Path(__file__).resolve()),
        "--gateway-child",
        str(lease_descriptor),
        requested,
    ]
    process = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=supervisor_env,
        start_new_session=True,
        pass_fds=(lease_descriptor,),
    )
    try:
        stdout, stderr = _capture_gateway_output(
            process,
            token,
            (
                GATEWAY_TIMEOUT_SECONDS
                + GATEWAY_KILL_AFTER_SECONDS
                + GATEWAY_COMMUNICATE_GRACE_SECONDS
            ),
        )
    except BaseException:
        _terminate_gateway_group(process)
        raise
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def promote(requested: str, token: bytes) -> int:
    STATE_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = STATE_ROOT.lstat()
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_gid != 0
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise GatewayUpdateError("gateway update state root is unsafe")
    descriptor = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
    try:
        lock_metadata = os.fstat(descriptor)
        if lock_metadata.st_uid != 0 or lock_metadata.st_gid != 0 or stat.S_IMODE(lock_metadata.st_mode) != 0o600:
            raise GatewayUpdateError("gateway update lock is unsafe")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        _recover_interrupted_transaction()
        with tempfile.TemporaryDirectory(prefix="bears-plugin-gateway-source-", dir="/var/tmp") as source_root:
            source_directory = Path(source_root)
            os.chmod(source_directory, 0o700)
            repository = source_directory / "repository.git"
            _fetch_requested(repository, requested, token)
            blobs = _source_blobs(repository, requested)
            stage = _materialize_stage(PACKAGE_ROOT.parent, blobs, requested)
        try:
            _activate(stage, blobs[LAUNCHER_SOURCE], requested)
            try:
                result = _run_gateway(requested, token, descriptor)
            except Exception:
                _settle_active_gateway_after_failure(requested)
                raise
            if result.returncode:
                _settle_active_gateway_after_failure(requested)
                if result.stdout:
                    sys.stdout.buffer.write(result.stdout[:MAX_GATEWAY_OUTPUT])
                if result.stderr:
                    sys.stderr.buffer.write(result.stderr[:MAX_GATEWAY_OUTPUT])
                return result.returncode
            _commit_active_gateway(requested)
            if result.stdout:
                sys.stdout.buffer.write(result.stdout[:MAX_GATEWAY_OUTPUT])
            if result.stderr:
                sys.stderr.buffer.write(result.stderr[:MAX_GATEWAY_OUTPUT])
            return 0
        finally:
            if stage.exists():
                shutil.rmtree(stage, ignore_errors=True)
    finally:
        os.close(descriptor)


def main() -> int:
    try:
        os.umask(0o022)
        if os.geteuid() != 0 or pwd.getpwuid(os.geteuid()).pw_name != "root":
            raise GatewayUpdateError("gateway promoter must run as root")
        if len(sys.argv) == 4 and sys.argv[1] == "--gateway-child":
            _exec_gateway_child(sys.argv[2], sys.argv[3])
            raise GatewayUpdateError("supervised gateway child returned unexpectedly")
        if len(sys.argv) != 2 or SHA_RE.fullmatch(sys.argv[1]) is None:
            raise GatewayUpdateError("expected one exact lowercase 40-character SHA")
        token = _read_token()
        return promote(sys.argv[1], token)
    except GatewayUpdateError as exc:
        print(f"promote-gateway: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print("promote-gateway: unhandled privileged gateway update failure", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
