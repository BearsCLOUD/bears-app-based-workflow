#!/usr/bin/env python3
"""Atomically materialize the fixed deploy-gateway Sentry DSN from file descriptor 3."""

from __future__ import annotations

import os
from pathlib import Path
import pwd
import stat
import sys
import tempfile
from urllib import parse

INPUT_FD = 3
OWNER = "ai1"
BASE_DIR = Path("/home/ai1/.config/bears-app-based-workflow")
CREDENTIAL_DIR = BASE_DIR / "credentials"
TARGET = CREDENTIAL_DIR / "sentry-dsn"
MAX_SECRET_BYTES = 4096


class MaterializeError(RuntimeError):
    """Fail closed without exposing secret material."""


def read_secret() -> bytes:
    """Read one bounded value from the fixed inherited descriptor."""
    try:
        os.set_inheritable(INPUT_FD, False)
        raw = os.read(INPUT_FD, MAX_SECRET_BYTES + 1)
    except OSError as exc:
        raise MaterializeError("secret descriptor unavailable") from exc
    if not raw or len(raw) > MAX_SECRET_BYTES:
        raise MaterializeError("secret length outside boundary")
    value = raw.strip()
    if not value or any(byte in value for byte in (0, 10, 13, 32, 9)):
        raise MaterializeError("secret format outside boundary")
    try:
        parsed = parse.urlsplit(value.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise MaterializeError("secret format outside boundary") from exc
    parts = parsed.path.rstrip("/").rsplit("/", 1)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.username
        or len(parts) != 2
        or not parts[1].isdigit()
        or parsed.query
        or parsed.fragment
    ):
        raise MaterializeError("secret format outside boundary")
    return value + b"\n"


def require_safe_parent(path: Path, uid: int) -> None:
    """Require an existing operator-owned parent without writable peer access."""
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise MaterializeError("parent unavailable") from exc
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or path.is_symlink()
        or metadata.st_uid != uid
        or stat.S_IMODE(metadata.st_mode) & 0o022
    ):
        raise MaterializeError("parent boundary unsafe")


def private_directory(path: Path, uid: int, gid: int) -> None:
    """Create or normalize one fixed private directory."""
    try:
        path.mkdir(mode=0o700)
    except FileExistsError:
        pass
    except OSError as exc:
        raise MaterializeError("private directory unavailable") from exc
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode) or path.is_symlink():
        raise MaterializeError("private directory boundary unsafe")
    os.chown(path, uid, gid)
    os.chmod(path, 0o700)


def atomic_materialize(value: bytes, uid: int, gid: int) -> None:
    """Replace the target with an ai1-owned 0600 regular file."""
    descriptor = -1
    temporary = ""
    try:
        descriptor, temporary = tempfile.mkstemp(prefix=".sentry-dsn.", dir=CREDENTIAL_DIR)
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, TARGET)
        temporary = ""
        directory_fd = os.open(CREDENTIAL_DIR, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError as exc:
        raise MaterializeError("atomic materialization failed") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def main() -> int:
    if len(sys.argv) != 1 or os.geteuid() != 0:
        return 2
    try:
        account = pwd.getpwnam(OWNER)
        require_safe_parent(Path(account.pw_dir) / ".config", account.pw_uid)
        value = read_secret()
        private_directory(BASE_DIR, account.pw_uid, account.pw_gid)
        private_directory(CREDENTIAL_DIR, account.pw_uid, account.pw_gid)
        atomic_materialize(value, account.pw_uid, account.pw_gid)
    except (KeyError, MaterializeError, OSError):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
