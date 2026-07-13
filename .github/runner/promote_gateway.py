#!/usr/bin/env python3
"""Root-owned exact-SHA gateway updater and non-root promotion bridge.

This executable is installed once by ``install-runner.sh``.  It treats the
requested repository revision as data: it fetches only the fixed ``main``
history, materializes the hash-locked gateway in a root-owned staging tree,
and executes that gateway as ``ai1``.  A failed promotion restores the prior
gateway tree and launcher before returning the deployment failure.
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
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Mapping


REPOSITORY = "https://github.com/BearsCLOUD/bears-app-based-workflow.git"
MAIN_REF = "refs/remotes/origin/main"
SHA_RE = re.compile(r"[0-9a-f]{40}")
TOKEN_RE = re.compile(rb"[\x21-\x7e]+")
TOKEN_MAX_BYTES = 1024
SOURCE_PREFIX = ".github/runner/bears_deploy/"
LAUNCHER_SOURCE = ".github/runner/deploy_plugin.py"
LOCK_SOURCE = ".github/runner/sentry-requirements.lock"
PACKAGE_ROOT = Path("/usr/local/lib/bears-plugin-deploy")
LAUNCHER = Path("/usr/local/sbin/deploy-bears-app-based-workflow")
STATE_ROOT = Path("/var/lib/bears-plugin-gateway-update")
LOCK_FILE = STATE_ROOT / "update.lock"
JOURNAL_FILE = STATE_ROOT / "transaction.json"
PACKAGE_BACKUP = Path("/usr/local/lib/bears-plugin-deploy.previous")
LAUNCHER_BACKUP = Path("/usr/local/sbin/deploy-bears-app-based-workflow.previous")
GIT = "/usr/bin/git"
PYTHON = "/usr/bin/python3"
RUNUSER = "/usr/sbin/runuser"
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
ALLOWED_REQUIREMENTS = frozenset({"sentry-sdk", "urllib3", "certifi"})
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
    missing = expected - blobs
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
        _rollback()
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


def _run_gateway(requested: str, token: bytes) -> subprocess.CompletedProcess[bytes]:
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
    return _run(
        [RUNUSER, "-u", "ai1", "--", "/usr/bin/env", "-i", *child_env, str(LAUNCHER), requested],
        input_bytes=token,
        ok=tuple(range(256)),
        timeout=None,
    )


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
                result = _run_gateway(requested, token)
            except Exception:
                _rollback()
                raise
            if result.returncode:
                _rollback()
                if result.stdout:
                    sys.stdout.buffer.write(result.stdout[:MAX_GATEWAY_OUTPUT])
                if result.stderr:
                    sys.stderr.buffer.write(result.stderr[:MAX_GATEWAY_OUTPUT])
                return result.returncode
            _write_journal(requested, "committed")
            _remove_path(PACKAGE_BACKUP)
            _remove_path(LAUNCHER_BACKUP)
            JOURNAL_FILE.unlink(missing_ok=True)
            _sync_directory(PACKAGE_ROOT.parent)
            _sync_directory(LAUNCHER.parent)
            _sync_directory(STATE_ROOT)
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
